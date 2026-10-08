import QtQuick
import QtTest
import "../core/TOTP.js" as TOTPModel

TestCase {
    name: "TOTP"

    function test_rfc6238_sha1() {
        var secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        var timestamps = [59, 1111111109, 1111111111, 1234567890, 2000000000, 20000000000]
        var expected = ["94287082", "07081804", "14050471", "89005924", "69279037", "65353130"]

        for (var i = 0; i < timestamps.length; i++) {
            var code = TOTPModel.generateCode({
                secret: secret,
                digits: 8,
                period: 30,
                algorithm: "SHA1"
            }, new Date(timestamps[i] * 1000))
            compare(code.value, expected[i])
        }
    }

    function test_rfc6238_sha256() {
        var secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZA"
        var code = TOTPModel.generateCode({
            secret: secret,
            digits: 8,
            period: 30,
            algorithm: "SHA256"
        }, new Date(59 * 1000))
        compare(code.value, "46119246")
    }

    function test_rfc6238_sha512() {
        var secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZA"
        var code = TOTPModel.generateCode({
            secret: secret,
            digits: 8,
            period: 30,
            algorithm: "SHA512"
        }, new Date(59 * 1000))
        compare(code.value, "95592584")
    }

    function test_decode_base32() {
        compare(TOTPModel.normalizeSecret(" jbsw-y3dp == "), "JBSWY3DP")
        var decoded = TOTPModel.decodeBase32("JBSWY3DP")
        compare(decoded.length, 5)
        compare(decoded[0], 72) // 'H'
        compare(decoded[1], 101) // 'e'
        compare(decoded[2], 108) // 'l'
        compare(decoded[3], 108) // 'l'
        compare(decoded[4], 111) // 'o'
    }

    function test_parse_input() {
        var acc = TOTPModel.parseInput("otpauth://totp/GitHub:me%40example.com?secret=JBSWY3DP&issuer=GitHub&algorithm=SHA256&digits=8&period=45")
        compare(acc.name, "me@example.com")
        compare(acc.issuer, "GitHub")
        compare(acc.secret, "JBSWY3DP")
        compare(acc.digits, 8)
        compare(acc.period, 45)
        compare(acc.algorithm, "SHA256")

        var raw = TOTPModel.parseInput("JBSWY3DP", "My Account", "Google")
        compare(raw.name, "My Account")
        compare(raw.issuer, "Google")
        compare(raw.digits, 6)
        compare(raw.period, 30)
    }

    function test_parse_add() {
        var res1 = TOTPModel.parseAdd("add JBSWY3DP GitHub")
        verify(!res1.incomplete)
        compare(res1.account.name, "GitHub")
        compare(res1.account.secret, "JBSWY3DP")

        var res2 = TOTPModel.parseAdd("add otpauth://totp/GitLab:user?secret=JBSWY3DP")
        verify(!res2.incomplete)
        compare(res2.account.name, "user")
        compare(res2.account.issuer, "GitLab")

        var res3 = TOTPModel.parseAdd("add")
        verify(res3.incomplete)
    }

    function test_account_storage() {
        var accounts = []
        accounts = TOTPModel.addAccount(accounts, { name: "GitHub", secret: "JBSWY3DP", issuer: "GitHub" })
        compare(accounts.length, 1)
        compare(accounts[0].name, "GitHub")

        accounts = TOTPModel.addAccount(accounts, { name: "AWS", secret: "JBSWY3DP", issuer: "AWS" })
        compare(accounts.length, 2)
        compare(accounts[0].name, "AWS") // alphabetical sort

        var json = TOTPModel.serializeAccounts(accounts)
        var parsed = TOTPModel.readAccounts(json)
        compare(parsed.length, 2)
        compare(parsed[0].name, "AWS")

        accounts = TOTPModel.removeAccount(accounts, accounts[0].id)
        compare(accounts.length, 1)
        compare(accounts[0].name, "GitHub")
    }

    function test_palette_rows() {
        var accounts = [
            { id: "1", name: "GitHub", issuer: "GitHub", secret: "JBSWY3DP", digits: 6, period: 30, algorithm: "SHA1" }
        ]
        var settings = { notifyOnCopy: true }
        var now = 1234567890 * 1000

        // Root query empty -> navigation row
        var rootRows = TOTPModel.rows("", accounts, settings, now, false, "totp", false)
        compare(rootRows.length, 1)
        compare(rootRows[0].id, "open")
        compare(rootRows[0].action.type, "navigate")

        // Root query 'totp' -> navigation row
        var rootTotpRows = TOTPModel.rows("totp", accounts, settings, now, false, "totp", false)

        // Scoped query -> account row
        var scopedRows = TOTPModel.rows("", accounts, settings, now, true, "totp", false)
        verify(scopedRows.length >= 1)
        compare(scopedRows[0].id, "account/1")
        compare(scopedRows[0].verb, "Copy OTP")
        compare(scopedRows[0].altVerb, "Actions")

        // Account actions scope
        var actionRows = TOTPModel.rows("", accounts, settings, now, "totp/account/1", "totp", false)
        compare(actionRows.length, 6)
        compare(actionRows[0].id, "act-copy-otp/1")
        compare(actionRows[1].id, "act-paste-otp/1")
        compare(actionRows[2].id, "act-copy-secret/1")
        compare(actionRows[3].id, "act-copy-uri/1")
        compare(actionRows[4].id, "act-edit/1")
        compare(actionRows[5].id, "act-delete/1")
        verify(actionRows[5].confirm.length > 0)

        // Manage scope
        var manageRows = TOTPModel.rows("", accounts, settings, now, "totp/manage", "totp", false)
        compare(manageRows[0].id, "manage-add")

        // Quick OTP
        var quickRows = TOTPModel.rows("quick JBSWY3DP", accounts, settings, now, false, "totp", false)
        compare(quickRows[0].id, "quick-otp")
    }

    function test_account_update_and_uri() {
        var accounts = [
            { id: "1", name: "GitHub", issuer: "GitHub", secret: "JBSWY3DP", digits: 6, period: 30, algorithm: "SHA1" }
        ]
        var updated = TOTPModel.updateAccount(accounts, { id: "1", name: "GitHub (Work)", issuer: "GitHub", secret: "JBSWY3DP", digits: 8, period: 60, algorithm: "SHA256" })
        compare(updated.length, 1)
        compare(updated[0].name, "GitHub (Work)")
        compare(updated[0].digits, 8)
        compare(updated[0].period, 60)
        compare(updated[0].algorithm, "SHA256")

        var uri = TOTPModel.buildUri(updated[0])
        verify(uri.indexOf("otpauth://totp/GitHub:") >= 0)
        verify(uri.indexOf("digits=8") >= 0)
        verify(uri.indexOf("period=60") >= 0)
        verify(uri.indexOf("algorithm=SHA256") >= 0)
    }

    function test_search_in_root() {
        var accounts = [
            { id: "1", name: "GitHub", issuer: "GitHub", secret: "JBSWY3DP", digits: 6, period: 30, algorithm: "SHA1" }
        ]
        var now = 1234567890 * 1000

        // Default setting: searchInRoot = false
        var defaultSettings = { searchInRoot: false }
        var rootRowsDefault = TOTPModel.rows("github", accounts, defaultSettings, now, false, "totp", false)
        // Only navRow is returned, accounts are hidden at root
        compare(rootRowsDefault.length, 1)
        compare(rootRowsDefault[0].id, "open")

        // searchInRoot enabled: accounts are returned at root for fuzzy search
        var enabledSettings = { searchInRoot: true }
        var rootRowsEnabled = TOTPModel.rows("github", accounts, enabledSettings, now, false, "totp", false)
        compare(rootRowsEnabled.length, 2)
        compare(rootRowsEnabled[0].id, "open")
        compare(rootRowsEnabled[1].id, "account/1")

        // Scoped mode ignores searchInRoot setting and always searches accounts
        var scopedRows = TOTPModel.rows("github", accounts, defaultSettings, now, true, "totp", false)
        compare(scopedRows.length, 1)
        compare(scopedRows[0].id, "account/1")

        // Command mode (e.g. 'totp github') also always searches accounts
        var cmdRows = TOTPModel.rows("github", accounts, defaultSettings, now, false, "totp", true)
        compare(cmdRows.length, 1)
        compare(cmdRows[0].id, "account/1")
    }
}
