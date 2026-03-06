use std::process;

use super::{Command, Provider};

pub struct CalculatorProvider;

impl CalculatorProvider {
    pub fn new() -> Self {
        Self
    }
}

impl Provider for CalculatorProvider {
    fn id(&self) -> &str {
        "calculator"
    }

    fn commands(&self) -> Vec<Command> {
        Vec::new() // No static commands
    }

    fn execute(&self, command: &Command) {
        // data contains the result string — copy to clipboard via wl-copy
        let result = &command.data;
        let mut cmd = process::Command::new("wl-copy");
        cmd.arg(result);
        cmd.stdin(process::Stdio::null());
        cmd.stdout(process::Stdio::null());
        cmd.stderr(process::Stdio::null());
        if let Err(e) = cmd.spawn() {
            eprintln!("calculator: failed to copy to clipboard: {e}");
        }
    }

    fn query_commands(&self, query: &str) -> Vec<Command> {
        let trimmed = query.trim();
        if trimmed.is_empty() {
            return Vec::new();
        }

        // Try to evaluate the expression.
        match evaluate(trimmed) {
            Some(result) => {
                let display = format_result(result);
                vec![Command {
                    id: format!("calculator:{}", display),
                    label: format!("= {}", display),
                    keywords: vec![],
                    hotkey: Some("Copy to clipboard".to_string()),
                    provider: "calculator".to_string(),
                    data: display,
                }]
            }
            None => Vec::new(),
        }
    }
}

/// Format a result: show integers without decimals, floats with up to 10
/// significant decimal places (trimming trailing zeros).
fn format_result(value: f64) -> String {
    if value.is_nan() || value.is_infinite() {
        return value.to_string();
    }
    // If it's a clean integer, show without decimal point
    if value == value.floor() && value.abs() < 1e15 {
        format!("{}", value as i64)
    } else {
        // Trim trailing zeros from decimal representation
        let s = format!("{:.10}", value);
        let s = s.trim_end_matches('0');
        let s = s.trim_end_matches('.');
        s.to_string()
    }
}

// ---------------------------------------------------------------------------
// Expression evaluator — recursive descent parser
//
// Grammar:
//   expr     = term (('+' | '-') term)*
//   term     = power (('*' | '/' | '%') power)*
//   power    = unary ('^' power)?          (right-associative)
//   unary    = '-' unary | atom
//   atom     = NUMBER | '(' expr ')'
//
// Supports: +, -, *, /, %, ^ (power), parentheses, unary minus, decimals
// ---------------------------------------------------------------------------

struct Parser<'a> {
    input: &'a [u8],
    pos: usize,
}

impl<'a> Parser<'a> {
    fn new(input: &'a str) -> Self {
        Self {
            input: input.as_bytes(),
            pos: 0,
        }
    }

    fn parse(&mut self) -> Option<f64> {
        let result = self.expr()?;
        self.skip_whitespace();
        if self.pos < self.input.len() {
            return None; // Trailing garbage
        }
        Some(result)
    }

    fn peek(&self) -> Option<u8> {
        if self.pos < self.input.len() {
            Some(self.input[self.pos])
        } else {
            None
        }
    }

    fn advance(&mut self) {
        self.pos += 1;
    }

    fn skip_whitespace(&mut self) {
        while self.pos < self.input.len() && self.input[self.pos].is_ascii_whitespace() {
            self.pos += 1;
        }
    }

    fn expr(&mut self) -> Option<f64> {
        let mut left = self.term()?;
        loop {
            self.skip_whitespace();
            match self.peek() {
                Some(b'+') => {
                    self.advance();
                    left += self.term()?;
                }
                Some(b'-') => {
                    self.advance();
                    left -= self.term()?;
                }
                _ => break,
            }
        }
        Some(left)
    }

    fn term(&mut self) -> Option<f64> {
        let mut left = self.power()?;
        loop {
            self.skip_whitespace();
            match self.peek() {
                Some(b'*') => {
                    // Check for ** (power)
                    if self.pos + 1 < self.input.len() && self.input[self.pos + 1] == b'*' {
                        break; // Let power() handle **
                    }
                    self.advance();
                    left *= self.power()?;
                }
                Some(b'/') => {
                    self.advance();
                    let right = self.power()?;
                    if right == 0.0 {
                        return None; // Division by zero
                    }
                    left /= right;
                }
                Some(b'%') => {
                    self.advance();
                    let right = self.power()?;
                    if right == 0.0 {
                        return None;
                    }
                    left %= right;
                }
                _ => break,
            }
        }
        Some(left)
    }

    fn power(&mut self) -> Option<f64> {
        let base = self.unary()?;
        self.skip_whitespace();
        // ^ or **
        let is_power = match self.peek() {
            Some(b'^') => {
                self.advance();
                true
            }
            Some(b'*') if self.pos + 1 < self.input.len() && self.input[self.pos + 1] == b'*' => {
                self.advance();
                self.advance();
                true
            }
            _ => false,
        };
        if is_power {
            let exp = self.power()?; // Right-associative
            Some(base.powf(exp))
        } else {
            Some(base)
        }
    }

    fn unary(&mut self) -> Option<f64> {
        self.skip_whitespace();
        if self.peek() == Some(b'-') {
            self.advance();
            let val = self.unary()?;
            Some(-val)
        } else {
            self.atom()
        }
    }

    fn atom(&mut self) -> Option<f64> {
        self.skip_whitespace();
        match self.peek() {
            Some(b'(') => {
                self.advance();
                let val = self.expr()?;
                self.skip_whitespace();
                if self.peek() != Some(b')') {
                    return None; // Unmatched paren
                }
                self.advance();
                Some(val)
            }
            Some(c) if c.is_ascii_digit() || c == b'.' => self.number(),
            _ => None,
        }
    }

    fn number(&mut self) -> Option<f64> {
        let start = self.pos;
        while self.pos < self.input.len()
            && (self.input[self.pos].is_ascii_digit() || self.input[self.pos] == b'.')
        {
            self.pos += 1;
        }
        let s = std::str::from_utf8(&self.input[start..self.pos]).ok()?;
        s.parse::<f64>().ok()
    }
}

/// Try to evaluate a string as a math expression. Returns None if it's not
/// a valid expression.
fn evaluate(input: &str) -> Option<f64> {
    // Quick check: must contain at least one digit to be an expression
    if !input.bytes().any(|b| b.is_ascii_digit()) {
        return None;
    }
    let mut parser = Parser::new(input);
    let result = parser.parse()?;
    if result.is_nan() || result.is_infinite() {
        return None;
    }
    Some(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn basic_arithmetic() {
        assert_eq!(evaluate("42+7"), Some(49.0));
        assert_eq!(evaluate("42 + 7"), Some(49.0));
        assert_eq!(evaluate("10 - 3"), Some(7.0));
        assert_eq!(evaluate("6 * 7"), Some(42.0));
        assert_eq!(evaluate("100 / 4"), Some(25.0));
    }

    #[test]
    fn operator_precedence() {
        assert_eq!(evaluate("2 + 3 * 4"), Some(14.0));
        assert_eq!(evaluate("(2 + 3) * 4"), Some(20.0));
    }

    #[test]
    fn power() {
        assert_eq!(evaluate("2^10"), Some(1024.0));
        assert_eq!(evaluate("2**3"), Some(8.0));
        // Right-associative: 2^3^2 = 2^(3^2) = 2^9 = 512
        assert_eq!(evaluate("2^3^2"), Some(512.0));
    }

    #[test]
    fn unary_minus() {
        assert_eq!(evaluate("-5"), Some(-5.0));
        assert_eq!(evaluate("-5 + 10"), Some(5.0));
        assert_eq!(evaluate("-(3 + 4)"), Some(-7.0));
    }

    #[test]
    fn decimals() {
        assert_eq!(evaluate("3.14 * 2"), Some(6.28));
        assert_eq!(evaluate("0.1 + 0.2"), Some(0.1 + 0.2));
    }

    #[test]
    fn modulo() {
        assert_eq!(evaluate("10 % 3"), Some(1.0));
    }

    #[test]
    fn division_by_zero() {
        assert_eq!(evaluate("5 / 0"), None);
    }

    #[test]
    fn not_an_expression() {
        assert_eq!(evaluate("hello"), None);
        assert_eq!(evaluate("close window"), None);
        assert_eq!(evaluate(""), None);
    }

    #[test]
    fn format_integer() {
        assert_eq!(format_result(49.0), "49");
        assert_eq!(format_result(-7.0), "-7");
        assert_eq!(format_result(0.0), "0");
    }

    #[test]
    fn format_decimal() {
        assert_eq!(format_result(3.14), "3.14");
        assert_eq!(format_result(1.0 / 3.0), "0.3333333333");
    }

    #[test]
    fn nested_parens() {
        assert_eq!(evaluate("((2 + 3) * (4 - 1))"), Some(15.0));
    }

    #[test]
    fn complex_expression() {
        assert_eq!(evaluate("2 * (3 + 4) ^ 2"), Some(98.0));
    }
}
