from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from .structured import Diagnostic


@dataclass(frozen=True)
class DiagnosticDefinition:
    code: str
    category: str
    default_severity: str
    message_template: str
    doc_url: Optional[str] = None


_DEFINITIONS: Dict[str, DiagnosticDefinition] = {
    # Syntax
    "N3-0001": DiagnosticDefinition(
        code="N3-0001",
        category="syntax",
        default_severity="error",
        message_template="Syntax error: {detail}",
    ),
    # Lang-spec / structural
    "N3-1001": DiagnosticDefinition(
        code="N3-1001",
        category="lang-spec",
        default_severity="error",
        message_template="Missing required field '{field}' on {kind}",
    ),
    "N3-1002": DiagnosticDefinition(
        code="N3-1002",
        category="lang-spec",
        default_severity="warning",
        message_template="Unknown field '{field}' on {kind}",
    ),
    "N3-1003": DiagnosticDefinition(
        code="N3-1003",
        category="lang-spec",
        default_severity="error",
        message_template="Invalid child block '{child}' under {parent}",
    ),
    "N3-1004": DiagnosticDefinition(
        code="N3-1004",
        category="lang-spec",
        default_severity="error",
        message_template="Duplicate name '{name}' in scope {scope}",
    ),
    "N3-1005": DiagnosticDefinition(
        code="N3-1005",
        category="lang-spec",
        default_severity="error",
        message_template="Field '{field}' on {kind} has invalid type or value",
    ),
    "N3-1010": DiagnosticDefinition(
        code="N3-1010",
        category="lang-spec",
        default_severity="error",
        message_template="No declarations were found in the source file",
    ),
    # Semantic
    "N3-2001": DiagnosticDefinition(
        code="N3-2001",
        category="semantic",
        default_severity="error",
        message_template="Reference to unknown '{target_kind}' named '{target}'",
    ),
    "N3-2002": DiagnosticDefinition(
        code="N3-2002",
        category="semantic",
        default_severity="error",
        message_template="Invalid argument or parameter binding in {context}",
    ),
    "N3-3200": DiagnosticDefinition(
        code="N3-3200",
        category="semantic",
        default_severity="error",
        message_template="List builtin is not applicable to the provided type",
    ),
    "N3-3201": DiagnosticDefinition(
        code="N3-3201",
        category="semantic",
        default_severity="error",
        message_template="Filter predicate must evaluate to a boolean",
    ),
    "N3-3202": DiagnosticDefinition(
        code="N3-3202",
        category="semantic",
        default_severity="error",
        message_template="Map expression produced an invalid value",
    ),
    "N3-3203": DiagnosticDefinition(
        code="N3-3203",
        category="semantic",
        default_severity="error",
        message_template="'sum' requires a numeric list",
    ),
    "N3-3204": DiagnosticDefinition(
        code="N3-3204",
        category="semantic",
        default_severity="error",
        message_template="Cannot compare elements for sorting",
    ),
    "N3-3205": DiagnosticDefinition(
        code="N3-3205",
        category="semantic",
        default_severity="error",
        message_template="Index out of bounds",
    ),
    "N3-3300": DiagnosticDefinition(
        code="N3-3300",
        category="semantic",
        default_severity="error",
        message_template="Unknown record field",
    ),
    "N3-3301": DiagnosticDefinition(
        code="N3-3301",
        category="semantic",
        default_severity="error",
        message_template="Invalid record key",
    ),
    "N3F-1000": DiagnosticDefinition(
        code="N3F-1000",
        category="semantic",
        default_severity="error",
        message_template="Frame source missing",
    ),
    "N3F-1001": DiagnosticDefinition(
        code="N3F-1001",
        category="semantic",
        default_severity="error",
        message_template="Invalid frame configuration",
    ),
    "N3F-1002": DiagnosticDefinition(
        code="N3F-1002",
        category="semantic",
        default_severity="error",
        message_template="Unknown column in frame select clause",
    ),
    "N3F-1003": DiagnosticDefinition(
        code="N3F-1003",
        category="semantic",
        default_severity="error",
        message_template="Frame where clause must evaluate to boolean",
    ),
    "N3F-1100": DiagnosticDefinition(
        code="N3F-1100",
        category="semantic",
        default_severity="error",
        message_template="Frame is not loaded or cannot be resolved",
    ),
    "N3F-1101": DiagnosticDefinition(
        code="N3F-1101",
        category="semantic",
        default_severity="error",
        message_template="List operation is not applicable to frame value",
    ),
    "N3F-1200": DiagnosticDefinition(
        code="N3F-1200",
        category="semantic",
        default_severity="error",
        message_template="Invalid frame expression in aggregate",
    ),
    "N3F-1201": DiagnosticDefinition(
        code="N3F-1201",
        category="semantic",
        default_severity="error",
        message_template="Invalid mapping expression for frame",
    ),
    "N3-3400": DiagnosticDefinition(
        code="N3-3400",
        category="semantic",
        default_severity="error",
        message_template="For-each loop requires a list",
    ),
    "N3-3401": DiagnosticDefinition(
        code="N3-3401",
        category="semantic",
        default_severity="error",
        message_template="Repeat-up-to requires a numeric count",
    ),
    "N3-3402": DiagnosticDefinition(
        code="N3-3402",
        category="semantic",
        default_severity="error",
        message_template="Invalid loop bounds",
    ),
    "N3-4400": DiagnosticDefinition(
        code="N3-4400",
        category="semantic",
        default_severity="error",
        message_template="Success/error pattern used on a non-result value",
    ),
    "N3-4401": DiagnosticDefinition(
        code="N3-4401",
        category="semantic",
        default_severity="error",
        message_template="Multiple success patterns are unreachable",
    ),
    "N3-4402": DiagnosticDefinition(
        code="N3-4402",
        category="semantic",
        default_severity="error",
        message_template="Multiple error patterns are unreachable",
    ),
    "N3-4500": DiagnosticDefinition(
        code="N3-4500",
        category="semantic",
        default_severity="error",
        message_template="Retry requires numeric max attempts",
    ),
    "N3-4501": DiagnosticDefinition(
        code="N3-4501",
        category="semantic",
        default_severity="error",
        message_template="Retry max attempts must be at least 1",
    ),
    "N3-4502": DiagnosticDefinition(
        code="N3-4502",
        category="semantic",
        default_severity="error",
        message_template="Retry used in unsupported context",
    ),
    "N3-4000": DiagnosticDefinition(
        code="N3-4000",
        category="semantic",
        default_severity="error",
        message_template="String builtin is not applicable to the provided type",
    ),
    "N3-4001": DiagnosticDefinition(
        code="N3-4001",
        category="semantic",
        default_severity="error",
        message_template="'join' requires a list of strings",
    ),
    "N3-4002": DiagnosticDefinition(
        code="N3-4002",
        category="semantic",
        default_severity="error",
        message_template="'split' requires a string separator",
    ),
    "N3-4003": DiagnosticDefinition(
        code="N3-4003",
        category="semantic",
        default_severity="error",
        message_template="'replace' arguments must be strings",
    ),
    "N3-4100": DiagnosticDefinition(
        code="N3-4100",
        category="semantic",
        default_severity="error",
        message_template="Aggregate requires a non-empty numeric list",
    ),
    "N3-4101": DiagnosticDefinition(
        code="N3-4101",
        category="semantic",
        default_severity="error",
        message_template="Invalid precision for 'round'",
    ),
    "N3-4102": DiagnosticDefinition(
        code="N3-4102",
        category="semantic",
        default_severity="error",
        message_template="Invalid type for numeric builtin",
    ),
    "N3-4200": DiagnosticDefinition(
        code="N3-4200",
        category="semantic",
        default_severity="error",
        message_template="'any'/'all' requires a list value",
    ),
    "N3-4201": DiagnosticDefinition(
        code="N3-4201",
        category="semantic",
        default_severity="error",
        message_template="Predicate for 'any'/'all' must evaluate to a boolean",
    ),
    "N3-4300": DiagnosticDefinition(
        code="N3-4300",
        category="semantic",
        default_severity="error",
        message_template="Invalid pattern in match statement",
    ),
    "N3-4301": DiagnosticDefinition(
        code="N3-4301",
        category="semantic",
        default_severity="error",
        message_template="Match requires a value expression",
    ),
    "N3-4302": DiagnosticDefinition(
        code="N3-4302",
        category="semantic",
        default_severity="error",
        message_template="Pattern type is incompatible with match value",
    ),
    "N3-4305": DiagnosticDefinition(
        code="N3-4305",
        category="semantic",
        default_severity="error",
        message_template="Builtin does not accept arguments",
    ),
    "N3-2101": DiagnosticDefinition(
        code="N3-2101",
        category="semantic",
        default_severity="error",
        message_template="Variable '{name}' is not defined",
    ),
    "N3-2102": DiagnosticDefinition(
        code="N3-2102",
        category="semantic",
        default_severity="error",
        message_template="Variable '{name}' is already defined",
    ),
    "N3-2103": DiagnosticDefinition(
        code="N3-2103",
        category="semantic",
        default_severity="error",
        message_template="Invalid operator or operand types for '{op}'",
    ),
    "N3-2104": DiagnosticDefinition(
        code="N3-2104",
        category="semantic",
        default_severity="error",
        message_template="Condition must evaluate to a boolean",
    ),
    "N3-2105": DiagnosticDefinition(
        code="N3-2105",
        category="semantic",
        default_severity="error",
        message_template="Divide-by-zero detected while evaluating expression",
    ),
    # Performance (reserved)
    "N3-3001": DiagnosticDefinition(
        code="N3-3001",
        category="performance",
        default_severity="warning",
        message_template="Potentially expensive chain detected",
    ),
    "N3-5000": DiagnosticDefinition(
        code="N3-5000",
        category="semantic",
        default_severity="error",
        message_template="Ask user label must be a string literal",
    ),
    "N3-5001": DiagnosticDefinition(
        code="N3-5001",
        category="semantic",
        default_severity="error",
        message_template="Invalid validation rule for user input",
    ),
    "N3-5010": DiagnosticDefinition(
        code="N3-5010",
        category="semantic",
        default_severity="error",
        message_template="Form label must be a string literal",
    ),
    "N3-5011": DiagnosticDefinition(
        code="N3-5011",
        category="semantic",
        default_severity="error",
        message_template="Duplicate field identifier in form",
    ),
    "N3-5012": DiagnosticDefinition(
        code="N3-5012",
        category="semantic",
        default_severity="error",
        message_template="Invalid field validation rule",
    ),
    "N3-5100": DiagnosticDefinition(
        code="N3-5100",
        category="semantic",
        default_severity="error",
        message_template="Invalid log level",
    ),
    "N3-5101": DiagnosticDefinition(
        code="N3-5101",
        category="semantic",
        default_severity="error",
        message_template="Log message must be a string literal",
    ),
    "N3-5110": DiagnosticDefinition(
        code="N3-5110",
        category="semantic",
        default_severity="error",
        message_template="Checkpoint label must be a string literal",
    ),
    "N3-6000": DiagnosticDefinition(
        code="N3-6000",
        category="semantic",
        default_severity="error",
        message_template="Unknown helper function",
    ),
    "N3-6001": DiagnosticDefinition(
        code="N3-6001",
        category="semantic",
        default_severity="error",
        message_template="Wrong number of arguments for helper",
    ),
    "N3-6002": DiagnosticDefinition(
        code="N3-6002",
        category="semantic",
        default_severity="error",
        message_template="Return used outside of helper",
    ),
    "N3-6003": DiagnosticDefinition(
        code="N3-6003",
        category="semantic",
        default_severity="error",
        message_template="Duplicate helper identifier",
    ),
    "N3-6100": DiagnosticDefinition(
        code="N3-6100",
        category="semantic",
        default_severity="error",
        message_template="Module not found",
    ),
    "N3-6101": DiagnosticDefinition(
        code="N3-6101",
        category="semantic",
        default_severity="error",
        message_template="Imported symbol not found in module",
    ),
    "N3-6102": DiagnosticDefinition(
        code="N3-6102",
        category="semantic",
        default_severity="error",
        message_template="Cyclic module import detected",
    ),
    "N3-6103": DiagnosticDefinition(
        code="N3-6103",
        category="semantic",
        default_severity="error",
        message_template="Duplicate import identifier",
    ),
    "N3-6200": DiagnosticDefinition(
        code="N3-6200",
        category="semantic",
        default_severity="error",
        message_template="Duplicate environment definition in settings",
    ),
    "N3-6201": DiagnosticDefinition(
        code="N3-6201",
        category="semantic",
        default_severity="error",
        message_template="Duplicate key inside env configuration",
    ),
    "N3-6202": DiagnosticDefinition(
        code="N3-6202",
        category="semantic",
        default_severity="error",
        message_template="Invalid expression in settings",
    ),
    "N3M-1000": DiagnosticDefinition(
        code="N3M-1000",
        category="semantic",
        default_severity="error",
        message_template="Macro missing description",
    ),
    "N3M-1001": DiagnosticDefinition(
        code="N3M-1001",
        category="semantic",
        default_severity="error",
        message_template="Duplicate macro name '{name}'",
    ),
    "N3M-1002": DiagnosticDefinition(
        code="N3M-1002",
        category="semantic",
        default_severity="error",
        message_template="Invalid macro clause",
    ),
    "N3M-1100": DiagnosticDefinition(
        code="N3M-1100",
        category="semantic",
        default_severity="error",
        message_template="Macro '{name}' not found",
    ),
    "N3M-1101": DiagnosticDefinition(
        code="N3M-1101",
        category="semantic",
        default_severity="error",
        message_template="Invalid macro argument '{name}'",
    ),
    "N3M-1102": DiagnosticDefinition(
        code="N3M-1102",
        category="semantic",
        default_severity="error",
        message_template="AI returned invalid or empty code for macro",
    ),
    "N3M-1103": DiagnosticDefinition(
        code="N3M-1103",
        category="semantic",
        default_severity="error",
        message_template="Macro expansion produced no declarations",
    ),
    "N3M-1200": DiagnosticDefinition(
        code="N3M-1200",
        category="semantic",
        default_severity="error",
        message_template="AI generation failed for macro",
    ),
    "N3M-1201": DiagnosticDefinition(
        code="N3M-1201",
        category="semantic",
        default_severity="error",
        message_template="AI output parse error: {detail}",
    ),
    "N3M-1202": DiagnosticDefinition(
        code="N3M-1202",
        category="semantic",
        default_severity="error",
        message_template="AI output failed lint checks",
    ),
    "N3M-1203": DiagnosticDefinition(
        code="N3M-1203",
        category="semantic",
        default_severity="error",
        message_template="Name conflict while merging macro expansion for '{name}'",
    ),
    "N3M-1300": DiagnosticDefinition(
        code="N3M-1300",
        category="semantic",
        default_severity="error",
        message_template="Macro expansion too large",
    ),
    "N3M-1301": DiagnosticDefinition(
        code="N3M-1301",
        category="semantic",
        default_severity="error",
        message_template="Disallowed syntax in macro expansion",
    ),
    "N3M-1302": DiagnosticDefinition(
        code="N3M-1302",
        category="semantic",
        default_severity="error",
        message_template="Recursive macro detected for '{name}'",
    ),
    "N3M-5000": DiagnosticDefinition(
        code="N3M-5000",
        category="semantic",
        default_severity="error",
        message_template="Macro 'crud_ui' requires a non-empty entity name",
    ),
    "N3M-5001": DiagnosticDefinition(
        code="N3M-5001",
        category="semantic",
        default_severity="error",
        message_template="Macro 'crud_ui' requires a list of fields",
    ),
    "N3M-5002": DiagnosticDefinition(
        code="N3M-5002",
        category="semantic",
        default_severity="error",
        message_template="Macro 'crud_ui' produced invalid code",
    ),
    "N3M-5003": DiagnosticDefinition(
        code="N3M-5003",
        category="semantic",
        default_severity="error",
        message_template="Macro 'crud_ui' produced naming conflicts",
    ),
    "N3U-1000": DiagnosticDefinition(
        code="N3U-1000",
        category="semantic",
        default_severity="error",
        message_template="Page must have a name",
    ),
    "N3U-1001": DiagnosticDefinition(
        code="N3U-1001",
        category="semantic",
        default_severity="error",
        message_template="Page route must begin with '/'",
    ),
    "N3U-1002": DiagnosticDefinition(
        code="N3U-1002",
        category="semantic",
        default_severity="error",
        message_template="Duplicate page name",
    ),
    "N3U-1003": DiagnosticDefinition(
        code="N3U-1003",
        category="semantic",
        default_severity="error",
        message_template="Duplicate route path",
    ),
    "N3U-1004": DiagnosticDefinition(
        code="N3U-1004",
        category="semantic",
        default_severity="error",
        message_template="Page must contain at least one layout element",
    ),
    "N3U-1100": DiagnosticDefinition(
        code="N3U-1100",
        category="semantic",
        default_severity="error",
        message_template="Duplicate section name on page",
    ),
    "N3U-1200": DiagnosticDefinition(
        code="N3U-1200",
        category="semantic",
        default_severity="error",
        message_template="Form not found for embedding",
    ),
    "N3U-1201": DiagnosticDefinition(
        code="N3U-1201",
        category="semantic",
        default_severity="error",
        message_template="Invalid form reference",
    ),
    "N3U-1300": DiagnosticDefinition(
        code="N3U-1300",
        category="semantic",
        default_severity="error",
        message_template="Layout element outside of a page or section",
    ),
    "N3U-2000": DiagnosticDefinition(
        code="N3U-2000",
        category="semantic",
        default_severity="error",
        message_template="State must be declared inside a page",
    ),
    "N3U-2001": DiagnosticDefinition(
        code="N3U-2001",
        category="semantic",
        default_severity="error",
        message_template="Duplicate state name on page",
    ),
    "N3U-2002": DiagnosticDefinition(
        code="N3U-2002",
        category="semantic",
        default_severity="error",
        message_template="Invalid state initializer",
    ),
    "N3U-2100": DiagnosticDefinition(
        code="N3U-2100",
        category="semantic",
        default_severity="error",
        message_template="Input must be inside a page or section",
    ),
    "N3U-2101": DiagnosticDefinition(
        code="N3U-2101",
        category="semantic",
        default_severity="error",
        message_template="Invalid input type",
    ),
    "N3U-2102": DiagnosticDefinition(
        code="N3U-2102",
        category="semantic",
        default_severity="error",
        message_template="Variable name conflicts with existing declaration",
    ),
    "N3U-2200": DiagnosticDefinition(
        code="N3U-2200",
        category="semantic",
        default_severity="error",
        message_template="Button must be inside a page or section",
    ),
    "N3U-2201": DiagnosticDefinition(
        code="N3U-2201",
        category="semantic",
        default_severity="error",
        message_template="Button must have an on click handler",
    ),
    "N3U-2202": DiagnosticDefinition(
        code="N3U-2202",
        category="semantic",
        default_severity="error",
        message_template="Invalid action in click handler",
    ),
    "N3U-2300": DiagnosticDefinition(
        code="N3U-2300",
        category="semantic",
        default_severity="error",
        message_template="Conditional must be inside a page or section",
    ),
    "N3U-2301": DiagnosticDefinition(
        code="N3U-2301",
        category="semantic",
        default_severity="error",
        message_template="Invalid conditional expression",
    ),
    "N3U-2302": DiagnosticDefinition(
        code="N3U-2302",
        category="semantic",
        default_severity="error",
        message_template="Empty or invalid conditional blocks",
    ),
    "N3U-3000": DiagnosticDefinition(
        code="N3U-3000",
        category="semantic",
        default_severity="error",
        message_template="Theme must be declared inside settings",
    ),
    "N3U-3001": DiagnosticDefinition(
        code="N3U-3001",
        category="semantic",
        default_severity="error",
        message_template="Invalid color literal",
    ),
    "N3U-3002": DiagnosticDefinition(
        code="N3U-3002",
        category="semantic",
        default_severity="error",
        message_template="Duplicate theme key",
    ),
    "N3U-3100": DiagnosticDefinition(
        code="N3U-3100",
        category="semantic",
        default_severity="error",
        message_template="Invalid color token",
    ),
    "N3U-3101": DiagnosticDefinition(
        code="N3U-3101",
        category="semantic",
        default_severity="error",
        message_template="Style directive is in an invalid position",
    ),
    "N3U-3200": DiagnosticDefinition(
        code="N3U-3200",
        category="semantic",
        default_severity="error",
        message_template="Invalid alignment keyword",
    ),
    "N3U-3201": DiagnosticDefinition(
        code="N3U-3201",
        category="semantic",
        default_severity="error",
        message_template="Alignment not allowed here",
    ),
    "N3U-3300": DiagnosticDefinition(
        code="N3U-3300",
        category="semantic",
        default_severity="error",
        message_template="Invalid layout type",
    ),
    "N3U-3400": DiagnosticDefinition(
        code="N3U-3400",
        category="semantic",
        default_severity="error",
        message_template="Invalid spacing size",
    ),
    "N3U-3401": DiagnosticDefinition(
        code="N3U-3401",
        category="semantic",
        default_severity="error",
        message_template="Spacing directive is outside a UI block",
    ),
    "N3U-3500": DiagnosticDefinition(
        code="N3U-3500",
        category="semantic",
        default_severity="error",
        message_template="Component name conflicts with existing declaration",
    ),
    "N3U-3501": DiagnosticDefinition(
        code="N3U-3501",
        category="semantic",
        default_severity="error",
        message_template="Component render block is missing",
    ),
    "N3U-3502": DiagnosticDefinition(
        code="N3U-3502",
        category="semantic",
        default_severity="error",
        message_template="Invalid component parameter list",
    ),
    "N3U-3600": DiagnosticDefinition(
        code="N3U-3600",
        category="semantic",
        default_severity="error",
        message_template="Component not found",
    ),
    "N3U-3601": DiagnosticDefinition(
        code="N3U-3601",
        category="semantic",
        default_severity="error",
        message_template="Component argument mismatch",
    ),
    "N3U-3602": DiagnosticDefinition(
        code="N3U-3602",
        category="semantic",
        default_severity="error",
        message_template="Unknown component parameter",
    ),
}


def get_definition(code: str) -> Optional[DiagnosticDefinition]:
    return _DEFINITIONS.get(code)


def all_definitions() -> Iterable[DiagnosticDefinition]:
    return _DEFINITIONS.values()


def create_diagnostic(
    code: str,
    *,
    message_kwargs: Optional[Dict[str, Any]] = None,
    file: Optional[str] = None,
    line: Optional[int] = None,
    column: Optional[int] = None,
    end_line: Optional[int] = None,
    end_column: Optional[int] = None,
    hint: Optional[str] = None,
) -> Diagnostic:
    definition = get_definition(code)
    if not definition:
        raise ValueError(f"Unknown diagnostic code '{code}'")
    kwargs = message_kwargs or {}
    message = definition.message_template.format(**kwargs)
    return Diagnostic(
        code=definition.code,
        category=definition.category,
        severity=definition.default_severity,
        message=message,
        hint=hint,
        file=file,
        line=line,
        column=column,
        end_line=end_line,
        end_column=end_column,
        doc_url=definition.doc_url,
    )
