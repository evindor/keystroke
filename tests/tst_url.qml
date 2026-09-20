import QtQuick
import QtTest
import "../core/Url.js" as Url
import "../providers"

TestCase {
    name: "OpenUrl"
    OpenUrl { id: service }

    function test_recognize_data() {
        return [
            {tag: "domain", input: "example.com", url: "https://example.com"},
            {tag: "www", input: "www.example.co.uk", url: "https://www.example.co.uk"},
            {tag: "whitespace", input: " \n https://example.com/a?q=1#b \t", url: "https://example.com/a?q=1#b"},
            {tag: "http", input: "http://example.com/", url: "http://example.com/"},
            {tag: "case", input: "HTTPS://Example.COM/Case?Key=Value", url: "HTTPS://Example.COM/Case?Key=Value"},
            {tag: "suffix", input: "example.com:8443/a%2Fb?q=a+b&x=%26&x=2#part", url: "https://example.com:8443/a%2Fb?q=a+b&x=%26&x=2#part"},
            {tag: "query", input: "example.com?q=hello&next=https://other.org/a", url: "https://example.com?q=hello&next=https://other.org/a"},
            {tag: "fragment", input: "example.com#part", url: "https://example.com#part"},
            {tag: "relative", input: "//example.com/a?q=1", url: "https://example.com/a?q=1"},
            {tag: "idn", input: "例え.テスト/日本語?言語=日本語", url: "https://例え.テスト/日本語?言語=日本語"},
            {tag: "accented", input: "münchen.de", url: "https://münchen.de"},
            {tag: "punycode", input: "xn--bcher-kva.xn--p1ai", url: "https://xn--bcher-kva.xn--p1ai"},
            {tag: "root dot", input: "example.com./a", url: "https://example.com./a"},
            {tag: "localhost", input: "localhost:3000/path?x=1", url: "http://localhost:3000/path?x=1"},
            {tag: "local subdomain", input: "app.localhost:8000", url: "http://app.localhost:8000"},
            {tag: "ipv4", input: "192.168.1.1:8080/?a=1", url: "http://192.168.1.1:8080/?a=1"},
            {tag: "ipv6", input: "[::1]:3000/a", url: "http://[::1]:3000/a"},
            {tag: "ipv6 full", input: "https://[2001:db8:0:0:0:0:0:1]/", url: "https://[2001:db8:0:0:0:0:0:1]/"},
            {tag: "ipv4 mapped", input: "[::ffff:192.0.2.128]", url: "http://[::ffff:192.0.2.128]"},
            {tag: "local https", input: "https://localhost:3000", url: "https://localhost:3000"},
            {tag: "intranet scheme", input: "http://intranet/docs", url: "http://intranet/docs"},
            {tag: "intranet prefix", input: "intranet/docs", explicit: true, url: "https://intranet/docs"},
            {tag: "userinfo", input: "https://user:p%40ss@example.com/path", url: "https://user:p%40ss@example.com/path"},
            {tag: "literal shell text", input: "example.com/?x=$(id)&q='a';echo", url: "https://example.com/?x=$(id)&q='a';echo"},
            // File extensions that read as ordinary destinations stay addresses.
            {tag: "rust docs", input: "docs.rs", url: "https://docs.rs"},
            {tag: "io", input: "crates.io", url: "https://crates.io"},
            {tag: "app", input: "vercel.app", url: "https://vercel.app"},
            // A scheme, a prefix, a port or a path overrides the file-name guard.
            {tag: "file tail scheme", input: "https://readme.md", url: "https://readme.md"},
            {tag: "file tail prefix", input: "readme.md", explicit: true, url: "https://readme.md"},
            {tag: "file tail path", input: "readme.md/raw", url: "https://readme.md/raw"},
            {tag: "file tail port", input: "notes.txt:8080", url: "https://notes.txt:8080"}
        ]
    }
    function test_recognize(data) {
        var result = Url.parse(data.input, !!data.explicit)
        verify(result !== null, data.input)
        compare(result.url, data.url)
    }

    function test_reject_data() {
        return ["", "hello", "open browser", "search example.com", "user@example.com", "user@example.com/a", "2.5", "1.2.3",
            "256.1.1.1", "01.2.3.4", "example", "intranet/docs", "/tmp/example.com", "~/example.com", "https://", "http:///example.com",
            "https://?q=x", "https://#x", "https://-bad.com", "https://bad-.com", "https://a..com", "https://a_b.com",
            "example.c", "example.123", "example.com:", "example.com:abc", "example.com:0", "example.com:65536",
            "[:::1]", "[1::2::3]", "[1::2:]", "[:1:2:3:4:5:6:7]", "[1:2:3:4:5:6:7]", "[1:2:3:4:5:6:7:8:9]",
            "[::ffff:999.0.0.1]", "[gg::1]", "[::1", "::1", "https://example.com\\evil", "https://example.com/a\nb",
            "example.com/a b", "example.com/\u0000", "javascript:alert(1)", "data:text/html,test", "file:///tmp/a", "ftp://example.com",
            "mailto:user@example.com", "https://a@b@example.com", "https://@example.com", "https://example.com/<script>",
            // A bare file name outranks a file match if it is offered as a URL.
            "readme.md", "notes.MD", "notes.md.", "package.json", "config.yaml", "photo.jpg", "report.pdf",
            "archive.zip", "video.mov", "script.sh", "main.py", "app.js", "index.html", "styles.css",
            "My.Report.PDF", "backup.tar", "libfoo.dll", "app.desktop", "query.sql"
        ].map(function(input, i) { return {tag: String(i) + ": " + input, input: input} })
    }
    function test_reject(data) { compare(Url.parse(data.input), null) }

    function test_provider_rows() {
        var row = service.provider.query({query: "example.com/a?q=1", scope: ""})[0]
        compare(row.action, {type: "url", url: "https://example.com/a?q=1"})
        compare(row.tier, "answer")
        verify(row.score >= 200)
        verify(!row.remember)
        compare(service.provider.query({query: "hello", scope: ""}), [])
        compare(service.provider.query({query: "example.com", scope: "files"}), [])
        var forced = service.provider.query({query: "go intranet", scope: "", command: {rest: "intranet", prefix: "go"}})[0]
        compare(forced.action.url, "https://intranet")
        var invalid = service.provider.query({query: "$javascript:alert(1)", scope: "", command: {rest: "javascript:alert(1)"}})[0]
        verify(invalid.disabled)
        compare(invalid.action.type, "noop")
        var empty = service.provider.query({query: "$", scope: "", command: {rest: ""}})[0]
        verify(empty.disabled)
    }
}
