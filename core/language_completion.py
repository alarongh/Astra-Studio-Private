from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CompletionTextEdit:
    start: int
    end: int
    new_text: str


@dataclass(frozen=True, slots=True)
class CompletionItem:
    label: str
    insert_text: str
    detail: str
    kind: str
    additional_edits: tuple[CompletionTextEdit, ...] = ()


@dataclass(frozen=True, slots=True)
class CompletionQuery:
    start: int
    end: int
    prefix: str
    items: tuple[CompletionItem, ...]


class CompletionProvider(Protocol):
    def complete(self, text: str, cursor_offset: int) -> CompletionQuery | None: ...


class CompletionRegistry:
    """Small language-neutral registry for built-in, offline completion providers."""

    def __init__(self) -> None:
        self._providers: dict[str, CompletionProvider] = {}

    def register(self, language: str, provider: CompletionProvider) -> None:
        self._providers[str(language)] = provider

    def complete(self, language: str, text: str, cursor_offset: int) -> CompletionQuery | None:
        provider = self._providers.get(str(language))
        if provider is None:
            return None
        return provider.complete(str(text), max(0, min(len(text), int(cursor_offset))))


JAVA_KEYWORDS = (
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class",
    "const", "continue", "default", "do", "double", "else", "enum", "exports", "extends",
    "final", "finally", "float", "for", "goto", "if", "implements", "import", "instanceof",
    "int", "interface", "long", "module", "native", "new", "non-sealed", "open", "opens",
    "package", "permits", "private", "protected", "provides", "public", "record", "requires",
    "return", "sealed", "short", "static", "strictfp", "super", "switch", "synchronized", "this",
    "throw", "throws", "to", "transient", "transitive", "try", "uses", "var", "void", "volatile",
    "when", "while", "with", "yield", "true", "false", "null",
)

JAVA_STANDARD_CLASSES: dict[str, str] = {
    "ArrayList": "java.util.ArrayList",
    "ArrayDeque": "java.util.ArrayDeque",
    "Arrays": "java.util.Arrays",
    "BigDecimal": "java.math.BigDecimal",
    "BigInteger": "java.math.BigInteger",
    "BufferedReader": "java.io.BufferedReader",
    "BufferedWriter": "java.io.BufferedWriter",
    "Collectors": "java.util.stream.Collectors",
    "Collections": "java.util.Collections",
    "Comparator": "java.util.Comparator",
    "CompletableFuture": "java.util.concurrent.CompletableFuture",
    "ConcurrentHashMap": "java.util.concurrent.ConcurrentHashMap",
    "DateTimeFormatter": "java.time.format.DateTimeFormatter",
    "Deque": "java.util.Deque",
    "Duration": "java.time.Duration",
    "ExecutorService": "java.util.concurrent.ExecutorService",
    "Executors": "java.util.concurrent.Executors",
    "File": "java.io.File",
    "HashMap": "java.util.HashMap",
    "HashSet": "java.util.HashSet",
    "IOException": "java.io.IOException",
    "InputStreamReader": "java.io.InputStreamReader",
    "Instant": "java.time.Instant",
    "Iterator": "java.util.Iterator",
    "LinkedHashMap": "java.util.LinkedHashMap",
    "LinkedHashSet": "java.util.LinkedHashSet",
    "LinkedList": "java.util.LinkedList",
    "List": "java.util.List",
    "Map": "java.util.Map",
    "Matcher": "java.util.regex.Matcher",
    "Objects": "java.util.Objects",
    "Optional": "java.util.Optional",
    "Scanner": "java.util.Scanner",
    "Set": "java.util.Set",
    "Pattern": "java.util.regex.Pattern",
    "PrintWriter": "java.io.PrintWriter",
    "Queue": "java.util.Queue",
    "Random": "java.util.Random",
    "ScheduledExecutorService": "java.util.concurrent.ScheduledExecutorService",
    "Stream": "java.util.stream.Stream",
    "StringJoiner": "java.util.StringJoiner",
    "StringTokenizer": "java.util.StringTokenizer",
    "TreeMap": "java.util.TreeMap",
    "TreeSet": "java.util.TreeSet",
    "UUID": "java.util.UUID",
    "LocalDate": "java.time.LocalDate",
    "LocalDateTime": "java.time.LocalDateTime",
    "ZonedDateTime": "java.time.ZonedDateTime",
    "Path": "java.nio.file.Path",
    "Files": "java.nio.file.Files",
    "URI": "java.net.URI",
    "URL": "java.net.URL",
    "Math": "java.lang.Math",
    "Runtime": "java.lang.Runtime",
    "StringBuilder": "java.lang.StringBuilder",
    "System": "java.lang.System",
    "Thread": "java.lang.Thread",
}

JAVA_MEMBERS: dict[str, tuple[str, ...]] = {
    "String": (
        "charAt()", "chars()", "codePoints()", "compareTo()", "concat()", "contains()", "endsWith()",
        "equals()", "equalsIgnoreCase()", "formatted()", "getBytes()", "indexOf()", "intern()", "isBlank()",
        "isEmpty()", "lastIndexOf()", "length()", "lines()", "matches()", "regionMatches()", "repeat()",
        "replace()", "replaceAll()", "replaceFirst()", "split()", "startsWith()", "strip()", "stripIndent()",
        "substring()", "toCharArray()", "toLowerCase()", "toUpperCase()", "trim()",
    ),
    "Array": ("length",),
    "List": ("add()", "addAll()", "clear()", "contains()", "containsAll()", "forEach()", "get()", "indexOf()", "isEmpty()", "iterator()", "lastIndexOf()", "listIterator()", "remove()", "removeIf()", "replaceAll()", "set()", "size()", "sort()", "spliterator()", "stream()", "subList()", "toArray()"),
    "ArrayList": ("add()", "addAll()", "clear()", "clone()", "contains()", "ensureCapacity()", "forEach()", "get()", "indexOf()", "isEmpty()", "iterator()", "remove()", "removeIf()", "replaceAll()", "set()", "size()", "sort()", "stream()", "subList()", "toArray()", "trimToSize()"),
    "Map": ("clear()", "compute()", "computeIfAbsent()", "computeIfPresent()", "containsKey()", "containsValue()", "entrySet()", "forEach()", "get()", "getOrDefault()", "isEmpty()", "keySet()", "merge()", "put()", "putAll()", "putIfAbsent()", "remove()", "replace()", "replaceAll()", "size()", "values()"),
    "HashMap": ("clear()", "clone()", "compute()", "computeIfAbsent()", "computeIfPresent()", "containsKey()", "containsValue()", "entrySet()", "forEach()", "get()", "getOrDefault()", "isEmpty()", "keySet()", "merge()", "put()", "putAll()", "putIfAbsent()", "remove()", "replace()", "replaceAll()", "size()", "values()"),
    "Set": ("add()", "addAll()", "clear()", "contains()", "containsAll()", "forEach()", "isEmpty()", "iterator()", "remove()", "removeAll()", "removeIf()", "retainAll()", "size()", "spliterator()", "stream()", "toArray()"),
    "Scanner": ("close()", "hasNext()", "hasNextDouble()", "hasNextInt()", "next()", "nextBoolean()", "nextDouble()", "nextInt()", "nextLine()", "useDelimiter()"),
    "StringBuilder": ("append()", "charAt()", "delete()", "insert()", "length()", "replace()", "reverse()", "setCharAt()", "substring()", "toString()"),
    "Optional": ("filter()", "flatMap()", "get()", "ifPresent()", "isEmpty()", "isPresent()", "map()", "orElse()", "orElseGet()", "orElseThrow()"),
    "Path": ("getFileName()", "getName()", "getParent()", "isAbsolute()", "normalize()", "resolve()", "toAbsolutePath()", "toFile()", "toString()"),
    "LocalDate": ("atStartOfDay()", "compareTo()", "getDayOfMonth()", "getMonth()", "getYear()", "isAfter()", "isBefore()", "minusDays()", "plusDays()"),
    "LocalDateTime": ("format()", "getDayOfMonth()", "getHour()", "getMinute()", "getMonth()", "getYear()", "isAfter()", "isBefore()", "minusDays()", "plusDays()", "toLocalDate()", "toLocalTime()"),
    "PrintStream": ("append()", "close()", "flush()", "format()", "print()", "printf()", "println()", "write()"),
    "Math": ("abs()", "ceil()", "clamp()", "cos()", "floor()", "max()", "min()", "pow()", "random()", "round()", "sin()", "sqrt()"),
    "Arrays": ("asList()", "binarySearch()", "copyOf()", "equals()", "fill()", "sort()", "stream()", "toString()"),
    "Collections": ("binarySearch()", "copy()", "frequency()", "max()", "min()", "reverse()", "shuffle()", "sort()", "unmodifiableList()"),
    "Files": ("copy()", "createDirectories()", "createFile()", "delete()", "exists()", "lines()", "move()", "readAllBytes()", "readString()", "writeString()"),
    "Stream": ("allMatch()", "anyMatch()", "collect()", "count()", "distinct()", "dropWhile()", "filter()", "findAny()", "findFirst()", "flatMap()", "forEach()", "limit()", "map()", "max()", "min()", "noneMatch()", "peek()", "reduce()", "skip()", "sorted()", "takeWhile()", "toArray()", "toList()"),
    "CompletableFuture": ("acceptEither()", "allOf()", "anyOf()", "cancel()", "complete()", "exceptionally()", "get()", "handle()", "isDone()", "join()", "runAsync()", "supplyAsync()", "thenAccept()", "thenApply()", "thenCombine()", "thenCompose()", "thenRun()", "whenComplete()"),
    "ExecutorService": ("awaitTermination()", "close()", "invokeAll()", "invokeAny()", "isShutdown()", "isTerminated()", "shutdown()", "shutdownNow()", "submit()"),
    "Pattern": ("compile()", "flags()", "matcher()", "matches()", "pattern()", "quote()", "split()"),
    "Matcher": ("appendReplacement()", "appendTail()", "end()", "find()", "group()", "groupCount()", "lookingAt()", "matches()", "replaceAll()", "replaceFirst()", "reset()", "start()"),
    "BigDecimal": ("abs()", "add()", "compareTo()", "divide()", "max()", "min()", "movePointLeft()", "movePointRight()", "multiply()", "negate()", "pow()", "remainder()", "round()", "scale()", "setScale()", "subtract()", "toBigInteger()", "toPlainString()"),
    "Thread": ("getId()", "getName()", "getState()", "interrupt()", "isAlive()", "isInterrupted()", "join()", "run()", "setDaemon()", "setName()", "sleep()", "start()"),
    "System": ("arraycopy()", "currentTimeMillis()", "exit()", "gc()", "getenv()", "getProperty()", "lineSeparator()", "nanoTime()", "setProperty()"),
    "Objects": ("checkIndex()", "deepEquals()", "equals()", "hash()", "hashCode()", "isNull()", "nonNull()", "requireNonNull()", "toString()"),
    "Executors": ("newCachedThreadPool()", "newFixedThreadPool()", "newScheduledThreadPool()", "newSingleThreadExecutor()", "newSingleThreadScheduledExecutor()", "newVirtualThreadPerTaskExecutor()"),
}

JAVA_STATIC_RECEIVERS = {
    "System.out": "PrintStream",
    "System.err": "PrintStream",
    "Math": "Math",
    "Arrays": "Arrays",
    "Collections": "Collections",
    "Files": "Files",
    "Objects": "Objects",
    "Pattern": "Pattern",
    "CompletableFuture": "CompletableFuture",
    "Executors": "Executors",
    "System": "System",
}


CPP_KEYWORDS = (
    "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor", "bool", "break",
    "case", "catch", "char", "char8_t", "char16_t", "char32_t", "class", "co_await", "co_return",
    "co_yield", "compl", "concept", "const", "consteval", "constexpr", "constinit", "const_cast",
    "continue", "decltype", "default", "delete", "do", "double", "dynamic_cast", "else", "enum",
    "explicit", "export", "extern", "false", "float", "for", "friend", "goto", "if", "inline", "int",
    "long", "module", "mutable", "namespace", "new", "noexcept", "not", "not_eq", "nullptr", "operator",
    "or", "or_eq", "private", "protected", "public", "register", "reinterpret_cast", "requires", "return",
    "short", "signed", "sizeof", "static", "static_assert", "static_cast", "struct", "switch", "template",
    "this", "thread_local", "throw", "true", "try", "typedef", "typeid", "typename", "union", "unsigned",
    "using", "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq",
)

CPP_STANDARD_SYMBOLS: dict[str, tuple[str, str]] = {
    "array": ("array", "array"),
    "deque": ("deque", "deque"),
    "forward_list": ("forward_list", "forward_list"),
    "list": ("list", "list"),
    "map": ("map", "map"),
    "multimap": ("multimap", "map"),
    "multiset": ("multiset", "set"),
    "priority_queue": ("priority_queue", "queue"),
    "queue": ("queue", "queue"),
    "set": ("set", "set"),
    "stack": ("stack", "stack"),
    "unordered_map": ("unordered_map", "unordered_map"),
    "unordered_set": ("unordered_set", "unordered_set"),
    "vector": ("vector", "vector"),
    "string": ("string", "string"),
    "string_view": ("string_view", "string_view"),
    "stringstream": ("stringstream", "sstream"),
    "ifstream": ("ifstream", "fstream"),
    "ofstream": ("ofstream", "fstream"),
    "fstream": ("fstream", "fstream"),
    "optional": ("optional", "optional"),
    "variant": ("variant", "variant"),
    "tuple": ("tuple", "tuple"),
    "pair": ("pair", "utility"),
    "unique_ptr": ("unique_ptr", "memory"),
    "shared_ptr": ("shared_ptr", "memory"),
    "weak_ptr": ("weak_ptr", "memory"),
    "make_unique": ("make_unique", "memory"),
    "make_shared": ("make_shared", "memory"),
    "function": ("function", "functional"),
    "filesystem": ("filesystem", "filesystem"),
    "thread": ("thread", "thread"),
    "mutex": ("mutex", "mutex"),
    "lock_guard": ("lock_guard", "mutex"),
    "future": ("future", "future"),
    "async": ("async", "future"),
    "sort": ("sort", "algorithm"),
    "stable_sort": ("stable_sort", "algorithm"),
    "find": ("find", "algorithm"),
    "find_if": ("find_if", "algorithm"),
    "transform": ("transform", "algorithm"),
    "accumulate": ("accumulate", "numeric"),
    "move": ("move", "utility"),
    "cout": ("cout", "iostream"),
    "cerr": ("cerr", "iostream"),
    "cin": ("cin", "iostream"),
    "endl": ("endl", "ostream"),
}

CPP_MEMBERS: dict[str, tuple[str, ...]] = {
    "string": ("append()", "at()", "back()", "begin()", "capacity()", "clear()", "compare()", "contains()", "data()", "empty()", "end()", "erase()", "find()", "find_first_of()", "find_last_of()", "front()", "insert()", "length()", "push_back()", "replace()", "reserve()", "resize()", "rfind()", "shrink_to_fit()", "size()", "starts_with()", "substr()", "swap()"),
    "string_view": ("at()", "back()", "begin()", "contains()", "data()", "empty()", "end()", "find()", "front()", "length()", "remove_prefix()", "remove_suffix()", "rfind()", "size()", "starts_with()", "substr()"),
    "vector": ("at()", "back()", "begin()", "capacity()", "cbegin()", "cend()", "clear()", "data()", "emplace()", "emplace_back()", "empty()", "end()", "erase()", "front()", "insert()", "pop_back()", "push_back()", "reserve()", "resize()", "shrink_to_fit()", "size()", "swap()"),
    "array": ("at()", "back()", "begin()", "cbegin()", "cend()", "data()", "empty()", "end()", "fill()", "front()", "size()", "swap()"),
    "deque": ("at()", "back()", "begin()", "clear()", "emplace_back()", "emplace_front()", "empty()", "end()", "erase()", "front()", "insert()", "pop_back()", "pop_front()", "push_back()", "push_front()", "resize()", "size()", "swap()"),
    "list": ("back()", "begin()", "clear()", "emplace_back()", "emplace_front()", "empty()", "end()", "erase()", "front()", "merge()", "pop_back()", "pop_front()", "push_back()", "push_front()", "remove()", "remove_if()", "reverse()", "size()", "sort()", "splice()", "unique()"),
    "map": ("at()", "begin()", "clear()", "contains()", "count()", "emplace()", "empty()", "end()", "erase()", "extract()", "find()", "insert()", "insert_or_assign()", "lower_bound()", "merge()", "size()", "swap()", "try_emplace()", "upper_bound()"),
    "unordered_map": ("at()", "begin()", "bucket_count()", "clear()", "contains()", "count()", "emplace()", "empty()", "end()", "erase()", "extract()", "find()", "insert()", "insert_or_assign()", "load_factor()", "merge()", "rehash()", "reserve()", "size()", "try_emplace()"),
    "set": ("begin()", "clear()", "contains()", "count()", "emplace()", "empty()", "end()", "erase()", "extract()", "find()", "insert()", "lower_bound()", "merge()", "size()", "upper_bound()"),
    "unordered_set": ("begin()", "bucket_count()", "clear()", "contains()", "count()", "emplace()", "empty()", "end()", "erase()", "extract()", "find()", "insert()", "load_factor()", "merge()", "rehash()", "reserve()", "size()"),
    "optional": ("and_then()", "emplace()", "has_value()", "or_else()", "reset()", "swap()", "transform()", "value()", "value_or()"),
    "unique_ptr": ("get()", "release()", "reset()", "swap()"),
    "shared_ptr": ("get()", "owner_before()", "reset()", "swap()", "unique()", "use_count()"),
    "weak_ptr": ("expired()", "lock()", "owner_before()", "reset()", "swap()", "use_count()"),
    "ifstream": ("close()", "eof()", "fail()", "good()", "is_open()", "open()", "peek()", "read()", "seekg()", "tellg()"),
    "ofstream": ("close()", "fail()", "flush()", "good()", "is_open()", "open()", "put()", "seekp()", "tellp()", "write()"),
    "stringstream": ("clear()", "eof()", "fail()", "good()", "str()", "swap()"),
    "path": ("append()", "clear()", "concat()", "empty()", "extension()", "filename()", "generic_string()", "has_extension()", "is_absolute()", "lexically_normal()", "parent_path()", "remove_filename()", "replace_extension()", "root_path()", "stem()", "string()"),
    "thread": ("detach()", "get_id()", "hardware_concurrency()", "join()", "joinable()", "native_handle()", "swap()"),
    "future": ("get()", "share()", "valid()", "wait()", "wait_for()", "wait_until()"),
    "ostream": ("flush()", "good()", "put()", "seekp()", "tellp()", "write()"),
    "istream": ("eof()", "fail()", "get()", "getline()", "good()", "ignore()", "peek()", "read()", "seekg()", "tellg()"),
}

CPP_STATIC_RECEIVERS = {
    "std::cout": "ostream", "std::cerr": "ostream", "std::clog": "ostream",
    "cout": "ostream", "cerr": "ostream", "clog": "ostream",
    "std::cin": "istream", "cin": "istream",
}


CATALOG_COMPLETIONS: dict[str, tuple[str, ...]] = {
    "Python": (
        "and", "as", "assert", "async", "await", "break", "case", "class", "continue", "def", "del", "elif", "else", "except", "False", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "match", "None", "nonlocal", "not", "or", "pass", "raise", "return", "True", "try", "while", "with", "yield", "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "input", "int", "len", "list", "map", "max", "min", "open", "print", "range", "reversed", "set", "sorted", "str", "sum", "super", "tuple", "type", "zip",
    ),
    "C++": (
        "alignas", "auto", "bool", "break", "case", "catch", "char", "class", "const", "constexpr", "continue", "default", "delete", "do", "double", "else", "enum", "explicit", "extern", "false", "float", "for", "friend", "if", "inline", "int", "long", "namespace", "new", "nullptr", "operator", "override", "private", "protected", "public", "return", "short", "signed", "sizeof", "static", "std", "string", "struct", "switch", "template", "this", "throw", "true", "try", "typedef", "typename", "union", "unsigned", "using", "vector", "virtual", "void", "volatile", "while", "array", "cout", "cin", "cerr", "endl", "map", "optional", "set", "unordered_map", "unique_ptr", "shared_ptr", "make_unique", "make_shared",
    ),
    "JavaScript": (
        "async", "await", "break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete", "do", "else", "export", "extends", "false", "finally", "for", "from", "function", "if", "import", "in", "instanceof", "let", "new", "null", "of", "return", "static", "super", "switch", "this", "throw", "true", "try", "typeof", "undefined", "var", "void", "while", "yield", "Array", "Boolean", "Date", "Error", "JSON", "Map", "Math", "Number", "Object", "Promise", "RegExp", "Set", "String", "console", "document", "fetch", "window", "setInterval", "setTimeout",
    ),
    "TypeScript": (
        "abstract", "any", "as", "asserts", "async", "await", "boolean", "break", "case", "catch", "class", "const", "constructor", "continue", "declare", "default", "do", "else", "enum", "export", "extends", "false", "finally", "for", "from", "function", "implements", "import", "in", "infer", "interface", "is", "keyof", "let", "namespace", "never", "new", "null", "number", "object", "of", "private", "protected", "public", "readonly", "return", "satisfies", "static", "string", "super", "switch", "symbol", "this", "throw", "true", "try", "type", "typeof", "undefined", "unknown", "var", "void", "while", "yield", "Array", "Map", "Promise", "Record", "Set", "console", "fetch",
    ),
    "C#": (
        "abstract", "as", "async", "await", "base", "bool", "break", "byte", "case", "catch", "char", "class", "const", "continue", "decimal", "default", "delegate", "do", "double", "else", "enum", "event", "explicit", "extern", "false", "finally", "fixed", "float", "for", "foreach", "get", "global", "goto", "if", "implicit", "in", "init", "int", "interface", "internal", "is", "lock", "long", "namespace", "new", "null", "object", "operator", "out", "override", "params", "partial", "private", "protected", "public", "readonly", "record", "ref", "required", "return", "sbyte", "sealed", "set", "short", "sizeof", "stackalloc", "static", "string", "struct", "switch", "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked", "unsafe", "ushort", "using", "var", "virtual", "void", "volatile", "while", "Console", "DateTime", "Dictionary", "Enumerable", "HashSet", "List", "Math", "StringBuilder", "Task",
    ),
    "PHP": (
        "abstract", "and", "array", "as", "break", "callable", "case", "catch", "class", "clone", "const", "continue", "declare", "default", "do", "echo", "else", "elseif", "empty", "endfor", "endforeach", "endif", "endswitch", "endwhile", "enum", "extends", "false", "final", "finally", "fn", "for", "foreach", "function", "global", "goto", "if", "implements", "include", "include_once", "instanceof", "interface", "isset", "match", "namespace", "new", "null", "or", "print", "private", "protected", "public", "readonly", "require", "require_once", "return", "static", "switch", "throw", "trait", "true", "try", "unset", "use", "while", "xor", "yield",
    ),
    "PowerShell": (
        "begin", "break", "catch", "class", "continue", "data", "do", "dynamicparam", "else", "elseif", "end", "enum", "exit", "filter", "finally", "for", "foreach", "from", "function", "if", "in", "param", "process", "return", "switch", "throw", "trap", "try", "until", "using", "var", "while", "workflow", "Write-Host", "Write-Output", "Get-ChildItem", "Get-Command", "Get-Content", "Get-Item", "Join-Path", "New-Item", "Remove-Item", "Resolve-Path", "Set-Content", "Test-Path", "Where-Object", "ForEach-Object",
    ),
    "SQL": (
        "ADD", "ALTER", "AND", "AS", "ASC", "BEGIN", "BETWEEN", "BY", "CASE", "CHECK", "COLUMN", "COMMIT", "CONSTRAINT", "CREATE", "DATABASE", "DEFAULT", "DELETE", "DESC", "DISTINCT", "DROP", "ELSE", "END", "EXISTS", "FOREIGN", "FROM", "FULL", "GROUP", "HAVING", "IN", "INDEX", "INNER", "INSERT", "INTO", "IS", "JOIN", "KEY", "LEFT", "LIKE", "LIMIT", "NOT", "NULL", "ON", "OR", "ORDER", "OUTER", "PRIMARY", "REFERENCES", "RIGHT", "ROLLBACK", "SELECT", "SET", "TABLE", "THEN", "UNION", "UNIQUE", "UPDATE", "VALUES", "VIEW", "WHEN", "WHERE", "WITH", "AVG", "COUNT", "MAX", "MIN", "SUM",
    ),
    "HTML": (
        "article", "aside", "audio", "body", "button", "canvas", "div", "footer", "form", "head", "header", "html", "img", "input", "label", "link", "main", "meta", "nav", "option", "p", "script", "section", "select", "source", "span", "style", "table", "tbody", "td", "textarea", "th", "thead", "title", "tr", "ul", "video",
    ),
    "CSS": (
        "align-items", "animation", "background", "background-color", "border", "border-radius", "box-shadow", "box-sizing", "color", "cursor", "display", "filter", "flex", "flex-direction", "font-family", "font-size", "font-weight", "gap", "grid-template-columns", "height", "justify-content", "line-height", "margin", "max-height", "max-width", "min-height", "min-width", "opacity", "overflow", "padding", "position", "text-align", "text-decoration", "transform", "transition", "width", "z-index", "absolute", "block", "fixed", "flex", "grid", "hidden", "inline", "none", "relative", "sticky",
    ),
    "GDScript": (
        "and", "as", "assert", "await", "break", "breakpoint", "class", "class_name", "const", "continue", "elif", "else", "enum", "extends", "false", "for", "func", "if", "in", "is", "match", "not", "null", "or", "pass", "preload", "return", "self", "signal", "static", "super", "true", "var", "while", "yield", "Array", "Dictionary", "Node", "Node2D", "Node3D", "PackedScene", "Resource", "Vector2", "Vector3",
    ),
    "Luau": (
        "and", "break", "continue", "do", "else", "elseif", "end", "export", "false", "for", "function", "if", "in", "local", "nil", "not", "or", "repeat", "return", "self", "then", "true", "type", "typeof", "until", "while", "assert", "error", "ipairs", "next", "pairs", "pcall", "print", "require", "select", "setmetatable", "string", "table", "task", "tonumber", "tostring", "unpack", "xpcall",
    ),
    "Shell": (
        "case", "do", "done", "elif", "else", "esac", "export", "fi", "for", "function", "if", "in", "local", "readonly", "return", "select", "then", "time", "until", "while", "echo", "printf", "read", "set", "shift", "source", "test", "trap", "unset",
    ),
    "Dockerfile": (
        "ADD", "ARG", "CMD", "COPY", "ENTRYPOINT", "ENV", "EXPOSE", "FROM", "HEALTHCHECK", "LABEL", "MAINTAINER", "ONBUILD", "RUN", "SHELL", "STOPSIGNAL", "USER", "VOLUME", "WORKDIR",
    ),
}


def _java_code_context(text: str, cursor_offset: int) -> bool:
    """Return False inside Java strings, chars, line comments and block comments."""
    state = "code"
    escaped = False
    i = 0
    while i < cursor_offset:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < cursor_offset else ""
        if state == "line_comment":
            if ch in "\r\n":
                state = "code"
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 1
        elif state in {"string", "char"}:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif (state == "string" and ch == '"') or (state == "char" and ch == "'"):
                state = "code"
        elif ch == "/" and nxt == "/":
            state = "line_comment"
            i += 1
        elif ch == "/" and nxt == "*":
            state = "block_comment"
            i += 1
        elif ch == '"':
            state = "string"
        elif ch == "'":
            state = "char"
        i += 1
    return state == "code"


def _java_declared_symbols(text: str) -> tuple[dict[str, str], set[str]]:
    types: dict[str, str] = {}
    symbols: set[str] = set()
    type_pattern = r"[A-Za-z_$][\w$]*(?:\s*<[^;={}()]+>)?(?:\s*\[\s*\])?"
    for match in re.finditer(rf"\b({type_pattern})\s+([a-zA-Z_$][\w$]*)\s*(?=[=;,:\)])", text):
        raw_type, name = match.groups()
        is_array = bool(re.search(r"\[\s*\]\s*$", raw_type))
        base_type = re.sub(r"\s*<.*", "", raw_type).replace("[]", "").strip()
        if is_array:
            base_type += "[]"
        types[name] = base_type
        symbols.add(name)
    for match in re.finditer(r"\bvar\s+([a-zA-Z_$][\w$]*)\s*=\s*new\s+([A-Za-z_$][\w$]*)", text):
        name, inferred_type = match.groups()
        types[name] = inferred_type
        symbols.add(name)
    for pattern in (
        r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)",
        r"\b[A-Za-z_$][\w$<>\[\], ?]*\s+([a-zA-Z_$][\w$]*)\s*\(",
    ):
        symbols.update(match.group(1) for match in re.finditer(pattern, text))
    return types, symbols


def _java_import_edit(text: str, qualified_name: str) -> tuple[CompletionTextEdit, ...]:
    statement = f"import {qualified_name};"
    if re.search(rf"(?m)^\s*import\s+{re.escape(qualified_name)}\s*;", text):
        return ()
    if re.search(rf"(?m)^\s*import\s+{re.escape(qualified_name.rsplit('.', 1)[0])}\.\*\s*;", text):
        return ()
    imports = list(re.finditer(r"(?m)^\s*import\s+[\w.*]+\s*;\s*(?:\r?\n)?", text))
    if imports:
        offset = imports[-1].end()
        prefix = "" if offset == 0 or text[offset - 1] in "\r\n" else "\n"
        return (CompletionTextEdit(offset, offset, prefix + statement + "\n"),)
    package = re.search(r"(?m)^\s*package\s+[\w.]+\s*;\s*(?:\r?\n)?", text)
    if package:
        offset = package.end()
        return (CompletionTextEdit(offset, offset, "\n" + statement + "\n"),)
    return (CompletionTextEdit(0, 0, statement + "\n\n"),)


class JavaCompletionProvider:
    def complete(self, text: str, cursor_offset: int) -> CompletionQuery | None:
        if not _java_code_context(text, cursor_offset):
            return None
        before = text[:cursor_offset]
        member_match = re.search(r"([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\.([A-Za-z_$][\w$]*)?$", before)
        types, symbols = _java_declared_symbols(text)
        if member_match:
            receiver = member_match.group(1)
            prefix = member_match.group(2) or ""
            member_type = JAVA_STATIC_RECEIVERS.get(receiver) or types.get(receiver)
            if member_type and member_type.endswith("[]"):
                member_type = "Array"
            members = JAVA_MEMBERS.get(member_type or "", ())
            if receiver == "this":
                methods = {
                    match.group(1) + "()"
                    for match in re.finditer(
                        r"(?<![\w$])(?:(?:public|protected|private|static|final|abstract|synchronized|native)\s+)*"
                        r"(?:[A-Za-z_$][\w$<>, ?\[\].]*\s+)+([a-zA-Z_$][\w$]*)\s*\(",
                        text,
                    )
                    if match.group(1) not in {"if", "for", "while", "switch", "catch"}
                }
                members = tuple(dict.fromkeys((*members, *sorted(methods))))
            items = tuple(
                CompletionItem(member, member, f"{member_type} member", "member")
                for member in members if member.lower().startswith(prefix.lower())
            )
            return CompletionQuery(cursor_offset - len(prefix), cursor_offset, prefix, items) if items else None

        token_match = re.search(r"[A-Za-z_$][\w$]*$", before)
        if token_match is None:
            return None
        prefix = token_match.group(0)
        if len(prefix) < 2:
            return None
        lower_prefix = prefix.lower()
        items: list[CompletionItem] = []
        for word in JAVA_KEYWORDS:
            if word.lower().startswith(lower_prefix) and word != prefix:
                items.append(CompletionItem(word, word, "Java keyword", "keyword"))
        for name in sorted(symbols, key=str.lower):
            if name.lower().startswith(lower_prefix) and name != prefix:
                detail = f"local symbol · {types[name]}" if name in types else "document symbol"
                items.append(CompletionItem(name, name, detail, "symbol"))
        for name, qualified_name in JAVA_STANDARD_CLASSES.items():
            if name.lower().startswith(lower_prefix) and name != prefix:
                items.append(CompletionItem(
                    name,
                    name,
                    qualified_name,
                    "class",
                    () if qualified_name.startswith("java.lang.") else _java_import_edit(text, qualified_name),
                ))
        kind_order = {"symbol": 0, "keyword": 1, "class": 2}
        items.sort(key=lambda item: (kind_order.get(item.kind, 9), item.label.lower()))
        return CompletionQuery(token_match.start(), cursor_offset, prefix, tuple(items[:80])) if items else None


def _cpp_normalize_type(raw_type: str) -> str:
    value = re.sub(r"\b(?:const|volatile|typename)\b", "", raw_type)
    value = re.sub(r"[&*]+", "", value)
    value = re.sub(r"<.*", "", value).strip()
    value = value.removeprefix("std::")
    return value.rsplit("::", 1)[-1].strip()


def _cpp_declared_symbols(text: str) -> tuple[dict[str, str], set[str]]:
    types: dict[str, str] = {}
    symbols: set[str] = set()
    declaration = re.compile(
        r"\b((?:(?:const|volatile)\s+)*(?:(?:std::)?[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)"
        r"(?:\s*<[^;={}()]+>)?\s*[*&]*)\s+([A-Za-z_]\w*)\s*(?=[=;,):{])"
    )
    for match in declaration.finditer(text):
        raw_type, name = match.groups()
        normalized = _cpp_normalize_type(raw_type)
        if normalized not in CPP_KEYWORDS or normalized in {"auto", "bool", "char", "double", "float", "int", "long", "short", "unsigned"}:
            types[name] = normalized
            symbols.add(name)
    for match in re.finditer(
        r"\bauto\s+([A-Za-z_]\w*)\s*=\s*(?:std::)?(make_unique|make_shared)\s*<",
        text,
    ):
        name, factory = match.groups()
        types[name] = "unique_ptr" if factory == "make_unique" else "shared_ptr"
        symbols.add(name)
    for match in re.finditer(r"\b(?:class|struct|enum(?:\s+class)?)\s+([A-Za-z_]\w*)", text):
        symbols.add(match.group(1))
    for match in re.finditer(
        r"(?<![\w:])(?:[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*(?:\s*<[^;{}()]+>)?[&*\s]+)+([A-Za-z_]\w*)\s*\(",
        text,
    ):
        if match.group(1) not in {"if", "for", "while", "switch", "catch"}:
            symbols.add(match.group(1))
    return types, symbols


def _cpp_include_edit(text: str, header: str) -> tuple[CompletionTextEdit, ...]:
    statement = f"#include <{header}>"
    if re.search(rf"(?m)^\s*#\s*include\s*[<\"]{re.escape(header)}[>\"]", text):
        return ()
    includes = list(re.finditer(r"(?m)^\s*#\s*include\s*[<\"][^>\"\r\n]+[>\"]\s*(?:\r?\n)?", text))
    if includes:
        offset = includes[-1].end()
        prefix = "" if offset == 0 or text[offset - 1] in "\r\n" else "\n"
        return (CompletionTextEdit(offset, offset, prefix + statement + "\n"),)
    return (CompletionTextEdit(0, 0, statement + "\n\n"),)


class CppCompletionProvider:
    """Type-aware, offline C++20/23 completion with safe standard includes."""

    def complete(self, text: str, cursor_offset: int) -> CompletionQuery | None:
        if not _java_code_context(text, cursor_offset):
            return None
        before = text[:cursor_offset]
        types, symbols = _cpp_declared_symbols(text)
        member_match = re.search(
            r"((?:std::)?[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)(?:\.|->)([A-Za-z_]\w*)?$",
            before,
        )
        if member_match:
            receiver = member_match.group(1)
            prefix = member_match.group(2) or ""
            member_type = CPP_STATIC_RECEIVERS.get(receiver) or types.get(receiver)
            members = CPP_MEMBERS.get(member_type or "", ())
            if receiver in {"this", "std::this"}:
                document_methods = {
                    match.group(1) + "()"
                    for match in re.finditer(
                        r"(?<![\w:])(?:[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*(?:\s*<[^;{}()]+>)?[&*\s]+)+"
                        r"([A-Za-z_]\w*)\s*\(",
                        text,
                    )
                    if match.group(1) not in {"if", "for", "while", "switch", "catch"}
                }
                members = tuple(dict.fromkeys((*members, *sorted(document_methods))))
            items = tuple(
                CompletionItem(member, member, f"C++ {member_type or 'document'} member", "member")
                for member in members
                if member.casefold().startswith(prefix.casefold())
            )
            return CompletionQuery(cursor_offset - len(prefix), cursor_offset, prefix, items) if items else None

        token_match = re.search(r"[A-Za-z_]\w*$", before)
        if token_match is None:
            return None
        prefix = token_match.group(0)
        if len(prefix) < 2:
            return None
        lower_prefix = prefix.casefold()
        qualified = before[:token_match.start()].endswith("std::")
        using_std = bool(re.search(r"(?m)^\s*using\s+namespace\s+std\s*;", text))
        items: list[CompletionItem] = []
        if not qualified:
            for keyword in CPP_KEYWORDS:
                if keyword.casefold().startswith(lower_prefix) and keyword != prefix:
                    items.append(CompletionItem(keyword, keyword, "C++20/23 keyword", "keyword"))
            for name in sorted(symbols, key=str.casefold):
                if name.casefold().startswith(lower_prefix) and name != prefix:
                    detail = f"local symbol · {types[name]}" if name in types else "document symbol"
                    items.append(CompletionItem(name, name, detail, "symbol"))
        for name, (_insert_name, header) in CPP_STANDARD_SYMBOLS.items():
            if not name.casefold().startswith(lower_prefix) or name == prefix:
                continue
            insert_text = name if qualified or using_std or re.search(rf"\busing\s+std::{re.escape(name)}\s*;", text) else f"std::{name}"
            items.append(CompletionItem(name, insert_text, f"std::{name} · <{header}>", "standard", _cpp_include_edit(text, header)))
        kind_order = {"symbol": 0, "keyword": 1, "standard": 2}
        items.sort(key=lambda item: (kind_order.get(item.kind, 9), item.label.casefold()))
        return CompletionQuery(token_match.start(), cursor_offset, prefix, tuple(items[:100])) if items else None


def _generic_code_context(language: str, text: str, cursor_offset: int) -> bool:
    before = text[:cursor_offset]
    if language in {"C++", "JavaScript", "TypeScript", "C#", "PHP", "CSS", "Luau"}:
        return _java_code_context(text, cursor_offset)
    if language in {"HTML", "XML"}:
        return before.rfind("<!--") <= before.rfind("-->")
    line = before.rsplit("\n", 1)[-1]
    marker = "--" if language in {"SQL", "Luau"} else "#" if language in {"Python", "PowerShell", "GDScript", "Shell", "Dockerfile"} else ""
    quote = ""
    escaped = False
    for index, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
            continue
        if marker and line.startswith(marker, index):
            return False
    return not quote


class CatalogCompletionProvider:
    """Fast offline fallback for common language keywords and built-ins."""

    def __init__(self, language: str, words: tuple[str, ...]) -> None:
        self.language = language
        self.words = tuple(dict.fromkeys(words))

    def complete(self, text: str, cursor_offset: int) -> CompletionQuery | None:
        if not _generic_code_context(self.language, text, cursor_offset):
            return None
        before = text[:cursor_offset]
        token_match = re.search(r"[A-Za-z_$][\w$-]*$", before)
        if token_match is None:
            return None
        prefix = token_match.group(0)
        if len(prefix) < 2:
            return None
        lower_prefix = prefix.casefold()
        items = [
            CompletionItem(word, word, f"{self.language} · встроенная библиотека", "catalog")
            for word in self.words
            if word.casefold().startswith(lower_prefix) and word != prefix
        ]
        items.sort(key=lambda item: (len(item.label), item.label.casefold()))
        return CompletionQuery(token_match.start(), cursor_offset, prefix, tuple(items[:80])) if items else None


DEFAULT_COMPLETION_REGISTRY = CompletionRegistry()
DEFAULT_COMPLETION_REGISTRY.register("Java", JavaCompletionProvider())
DEFAULT_COMPLETION_REGISTRY.register("C++", CppCompletionProvider())
for _language, _words in CATALOG_COMPLETIONS.items():
    if _language in {"Java", "C++"}:
        continue
    DEFAULT_COMPLETION_REGISTRY.register(_language, CatalogCompletionProvider(_language, _words))


def completion_query(language: str, text: str, cursor_offset: int) -> CompletionQuery | None:
    return DEFAULT_COMPLETION_REGISTRY.complete(language, text, cursor_offset)
