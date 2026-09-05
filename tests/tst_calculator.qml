import QtQuick
import QtTest
import "../core/Calculator.js" as Calc

TestCase {
    name: "Calculator"
    function test_arithmetic_data() {
        return [
            {q: "2+3*4", v: 14}, {q: "(2+3)*4", v: 20}, {q: "sqrt(144)+15% of 80", v: 24},
            {q: "2^8", v: 256}, {q: "sin(pi/2)", v: 1}, {q: "100*5%", v: 5}, {q: "17%5", v: 2},
            {q: "128 * 1.24", v: 158.72}, {q: "-3 + 5", v: 2}, {q: "7 // 2", v: 3}, {q: "= 22", v: 22}
        ]
    }
    function test_arithmetic(d) { fuzzyCompare(Calc.calculate(d.q), d.v, 1e-9) }
    function test_untrusted_never_executes_data() {
        return [{q: "__import__('os').system('true')"}, {q: "(1).__class__"}, {q: "[0]*10000000"},
                {q: "9**9**9"}, {q: "1/0"}, {q: "sqrt(-1)"}, {q: "1e999"}, {q: "x"}, {q: "1 2"}]
    }
    function test_untrusted_never_executes(d) {
        var threw = false
        try { Calc.calculate(d.q) } catch (e) { threw = true }
        verify(threw, d.q)
    }
    function test_partial_and_bare_numbers() {
        compare(Calc.evaluate("22").value, 22)
        compare(Calc.evaluate("22+").partial, "22+")
        compare(Calc.evaluate("22+1").value, 23)
        compare(Calc.evaluate("22+123").value, 145)
        compare(Calc.evaluate("hello"), null)
        compare(Calc.evaluate("+"), null)
    }
    function test_format() {
        compare(Calc.format(12, 12), "12")
        compare(Calc.format(145, 12), "145")
        compare(Calc.format(158.72, 12), "158.72")
        compare(Calc.format(1/3, 4), "0.3333")
        compare(Calc.format(6.561679790026246, 12), "6.56167979003")
    }
}
