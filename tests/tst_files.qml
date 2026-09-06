import QtQuick
import QtTest
import "../core/Files.js" as Files

TestCase {
    name: "Files"
    property string home: "/home/me"
    property var both: ({ files: true, folders: true, hidden: false, limit: 10 })
    property string output: "/home/me/Documents/report.pdf\n/home/me/Documents/reports/\n/home/me/Pictures/report-cover.png\n" +
                            "/home/me/src/tool/docs/README.md\n/home/me/notes/weekly report notes.md\n/home/me/Documents/reports/budget.xlsx\n\n"

    function test_short_or_disabled_queries_never_spawn() {
        compare(Files.cacheKey("", both), null)
        compare(Files.cacheKey("r", both), null)
        compare(Files.cacheKey("  ", both), null)
        compare(Files.cacheKey("re", { files: false, folders: false, limit: 10 }), null)
        verify(Files.cacheKey("re", both) !== null)
        // The key ignores the limit and the scope; it changes with the kinds and the hidden flag.
        compare(Files.cacheKey("Report  PDF", both), Files.cacheKey("report pdf", { files: true, folders: true, limit: 3 }))
        verify(Files.cacheKey("re", both) !== Files.cacheKey("re", { files: true, folders: true, hidden: true }))
        verify(Files.cacheKey("re", both) !== Files.cacheKey("re", { files: true, folders: false }))
    }

    function test_argv_is_literal_and_bounded() {
        var a = Files.argv("--version report.pdf", home, both)
        compare(a[0], "fd")
        verify(a.indexOf("--full-path") > 0)
        verify(a.indexOf("--max-results") > 0)
        compare(a[a.indexOf("--base-directory") + 1], home)
        // Earlier words ride on --and=, the last is anchored to the name after --; a dash never becomes a flag.
        compare(a.slice(-3), ["--and=\\-\\-version", "--", "[^/]*report\\.pdf[^/]*$"])
        compare(Files.argv("a+b (c)", home, both).slice(-1), ["[^/]*\\(c\\)[^/]*$"])
        verify(a.indexOf("--hidden") < 0)
        compare(Files.argv("x", home, { files: true, folders: false }).join(" ").indexOf("--type f --type d"), -1)
        compare(Files.argv("x", home, { files: false, folders: true }).join(" ").indexOf("--type d") > 0, true)
        var hidden = Files.argv("x", home, { files: true, folders: true, hidden: true })
        verify(hidden.indexOf("--hidden") > 0)
        compare(hidden[hidden.indexOf("--exclude") + 1], ".git")
    }

    function test_parse_strips_the_home_prefix_and_marks_folders() {
        var entries = Files.parse(output, home)
        compare(entries.length, 6)
        compare(entries[0], { path: "/home/me/Documents/report.pdf", rel: "Documents/report.pdf", dir: false })
        compare(entries[1], { path: "/home/me/Documents/reports", rel: "Documents/reports", dir: true })
        compare(Files.parse("/elsewhere/report.pdf\n/home/me/\n", home).length, 0)
    }

    function test_rows_rank_names_first_and_respect_the_limit() {
        var entries = Files.parse(output, home)
        var rows = Files.rows("report", entries, both, false)
        // budget.xlsx carries "report" only in its folder: the last word has to be in the name.
        compare(rows.length, 4)
        compare(rows[0].title, "report.pdf")
        for (var t = 0; t < rows.length; t++) verify(rows[t].title !== "budget.xlsx")
        compare(Files.rows("reports budget", entries, both, false).map(function(r) { return r.title }), ["budget.xlsx"])
        // An exact name outranks a name that merely contains the word.
        verify(Files.rows("reports", entries, both, false)[0].score > rows[rows.length - 1].score)
        for (var i = 0; i < rows.length; i++) {
            compare(rows[i].section, "Files")
            compare(rows[i].tier, "item")
            verify(rows[i].score <= 120 * 0.55 + 1)
            verify(rows[i].score >= 12)
        }
        compare(Files.rows("report", entries, { files: true, folders: true, limit: 2 }, false).length, 2)
        compare(Files.rows("report", entries, { files: true, folders: true, limit: 2 }, true).length, 4)
    }

    function test_kinds_and_relative_words_filter_rows() {
        var entries = Files.parse(output, home)
        var files = Files.rows("report", entries, { files: true, folders: false, limit: 10 }, false)
        for (var i = 0; i < files.length; i++) verify(files[i].title !== "reports")
        var folders = Files.rows("report", entries, { files: false, folders: true, limit: 10 }, false)
        compare(folders.length, 1)
        compare(folders[0].title, "reports")
        compare(folders[0].verb, "Open folder")
        // fd matched "home" against the absolute path; the relative part has to contain every word.
        compare(Files.rows("home", entries, both, false).length, 0)
        compare(Files.rows("report notes", entries, both, false).length, 1)
        compare(Files.rows("docs readme", entries, both, false)[0].title, "README.md")
    }

    function test_effects_open_files_folders_and_terminals() {
        var entries = Files.parse(output, home)
        var file = Files.rows("report.pdf", entries, both, false)[0]
        compare(file.action, { type: "exec", argv: ["xdg-open", "/home/me/Documents/report.pdf"] })
        compare(file.altAction.argv, ["setsid", "uwsm-app", "--", "xdg-terminal-exec", "--dir=/home/me/Documents"])
        compare(file.subtitle, "~/Documents")
        compare(file.previewLabel, "FILE")
        verify(file.remember)
        var folder = Files.rows("reports", entries, both, false)[0]
        compare(folder.action.argv, ["xdg-open", "/home/me/Documents/reports"])
        compare(folder.altAction.argv[4], "--dir=/home/me/Documents/reports")
        compare(folder.subtitle, "~/Documents · Folder")
        compare(folder.previewLabel, "FOLDER")
        compare(folder.hint, "ctrl ↵ terminal")
        var image = Files.rows("cover", entries, both, false)[0]
        compare(image.previewImage, "/home/me/Pictures/report-cover.png")
        compare(file.previewImage, "")
    }
}
