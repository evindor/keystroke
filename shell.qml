import Quickshell
import Quickshell.Io

ShellRoot {
    Flint { id: palette }
    IpcHandler {
        target: "flint"
        function toggle(): void { palette.toggle() }
        function open(payload: string): void { palette.open(payload) }
        function close(): void { palette.close() }
        function ping(): string { return palette.ping() }
        function inspect(): string { return palette.inspect() }
        function capture(path: string): string { return palette.capture(path) }
        function select(delta: int): void { palette.select(delta) }
        function activate(): void { palette.activate() }
        function back(): void { palette.goBack(false) }
        function query(text: string): void { palette.setQuery(text) }
    }
}
