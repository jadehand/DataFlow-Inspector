from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
PAGES = FRONTEND / "pages"
MAX_PAGE_MODULE_LINES = 500
PAGE_INFRASTRUCTURE = {"index.js", "page-controller.js"}

DOMAINS = (
    "assets",
    "detail",
    "lineage",
    "imports",
    "compare",
    "impact",
    "assistant",
)
PAGE_ADAPTERS = DOMAINS + ("overview", "workflows", "metrics")

RUNTIME_OWNERS = {
    "assets": ("core.js", "renderAssetFlowOptions"),
    "detail": ("catalog.js", "renderTableDetail"),
    "lineage": ("core.js", "layoutNodes"),
    "imports": ("imports.js", "uploadZip"),
    "compare": ("impact.js", "runComparison"),
    "impact": ("impact.js", "runImpact"),
    "assistant": ("assistant.js", "ask"),
}
EVENT_OWNERS = (
    "session-events.js",
    "import-events.js",
    "catalog-events.js",
    "impact-events.js",
    "assistant-events.js",
)


def _source_files():
    return tuple(FRONTEND.rglob("*.js"))


def _read(path):
    return path.read_text(encoding="utf-8")


def _meaningful_lines(source):
    return [
        line
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("//")
    ]


def _is_static_template(path, source):
    if not re.search(r"(?:template|markup|shell)\.js$", path.name):
        return False
    return (
        not re.search(r"\b(?:function|fetch|subscribe|addEventListener)\b", source)
        and bool(re.search(r"\bexport\s+(?:const|default)\b", source))
    )


def _calls_api_alias(source, aliases):
    for alias in aliases:
        direct = rf"\b(?:context|runtime)\s*\.\s*apis\s*\.\s*{re.escape(alias)}\s*\.\s*\w+\s*\("
        has_binding = (
            re.search(
                rf"\{{[^}}]*\b{re.escape(alias)}\b[^}}]*\}}\s*="
                r"\s*(?:context|runtime)\s*\.\s*apis\b",
                source,
            )
            or re.search(
                rf"\b{re.escape(alias)}\b\s*="
                r"\s*(?:context|runtime)\s*\.\s*apis\s*\.",
                source,
            )
        )
        calls_bound_alias = re.search(
            rf"\b{re.escape(alias)}\s*\.\s*\w+\s*\(",
            source,
        )
        if re.search(direct, source) or (has_binding and calls_bound_alias):
            return True
    return False


def test_p1_domain_modules_exist():
    missing = []
    for domain in DOMAINS:
        for relative in (f"api/{domain}.js", f"pages/{domain}.js"):
            if not (FRONTEND / relative).is_file():
                missing.append(relative)

    required = (
        "router.js",
        "state/store.js",
        "state/live-store.js",
        "state/demo-store.js",
    )
    missing.extend(relative for relative in required if not (FRONTEND / relative).is_file())

    assert not missing, "P1 领域边界文件缺失:\n" + "\n".join(f"- {item}" for item in missing)


def test_product_app_is_reduced_to_compatibility_facade():
    path = FRONTEND / "product-app.js"
    line_count = len(_read(path).splitlines())
    assert line_count <= 300, (
        f"product-app.js 仍有 {line_count} 行；P1 要求降至 300 行以内，"
        "仅保留组合或临时兼容入口"
    )


def test_page_entries_are_lifecycle_adapters_not_second_business_owners():
    violations = []
    for domain in PAGE_ADAPTERS:
        path = FRONTEND / "pages" / f"{domain}.js"
        if not path.is_file():
            continue
        source = _read(path)
        required = ("createPageController", ".subscribe(", "return () =>")
        missing = [marker for marker in required if marker not in source]
        owns_business = re.search(
            r"\b(?:addEventListener|onclick|onchange|onsubmit|oninput)\b|\.apis\b",
            source,
        )
        if missing or owns_business:
            violations.append(f"pages/{domain}.js: 缺少生命周期清理或重复拥有业务事件/API")

    assert not violations, (
        "页面入口只负责生命周期；业务事件必须由唯一运行时模块拥有:\n"
        + "\n".join(f"- {item}" for item in violations)
    )


def test_runtime_modules_own_domain_behavior():
    violations = []
    runtime = PAGES / "runtime"
    for domain, (filename, behavior) in RUNTIME_OWNERS.items():
        path = runtime / filename
        source = _read(path) if path.is_file() else ""
        registration = re.search(
            rf"Object\.assign\s*\(\s*ctx\s*,\s*\{{.*?\b{re.escape(behavior)}\b",
            source,
            re.DOTALL,
        )
        if f"function {behavior}" not in source or not registration:
            violations.append(f"{domain}: runtime/{filename} 未注册 {behavior}")
    assert not violations, "领域实现没有落到运行时深模块:\n" + "\n".join(violations)


def test_engine_is_thin_and_domain_event_owners_are_disposable():
    engine = _read(PAGES / "runtime" / "engine.js")
    assert len(engine.splitlines()) <= 150, "runtime/engine.js 必须保持为薄装配器"
    assert not re.search(
        r"\b(?:addEventListener|onclick|onchange|onsubmit|oninput)\b",
        engine,
    ), "业务事件不得重新集中到 runtime/engine.js"

    event_root = PAGES / "runtime" / "events"
    violations = []
    for filename in EVENT_OWNERS:
        path = event_root / filename
        source = _read(path) if path.is_file() else ""
        if "createEventScope" not in source or "return () =>" not in source:
            violations.append(filename)
    assert not violations, (
        "领域事件模块必须拥有独立 EventScope 并返回 cleanup:\n"
        + "\n".join(f"- {item}" for item in violations)
    )


def test_pages_directory_has_no_oversized_business_module():
    violations = []
    for path in PAGES.rglob("*.js"):
        source = _read(path)
        if path.name in PAGE_INFRASTRUCTURE or _is_static_template(path, source):
            continue
        line_count = len(source.splitlines())
        if line_count > MAX_PAGE_MODULE_LINES:
            violations.append(
                f"{path.relative_to(FRONTEND)}: {line_count} 行，超过 {MAX_PAGE_MODULE_LINES} 行"
            )

    assert not violations, (
        "pages 下的业务模块必须按领域拆分，禁止把巨型总控改名迁移:\n"
        + "\n".join(f"- {item}" for item in violations)
    )


def test_pages_directory_forbids_shared_business_runtime_centers():
    forbidden_name = re.compile(
        r"(?:^|[-_.])(?:application|shared|global|common)[-_.]"
        r"(?:runtime|manager|service)(?:[-_.]|$)",
        re.IGNORECASE,
    )
    violations = [
        str(path.relative_to(FRONTEND))
        for path in PAGES.rglob("*.js")
        if forbidden_name.search(path.name)
    ]

    assert not violations, (
        "禁止 application-runtime/shared-runtime 等共享业务中心；"
        "跨页面装配必须保持薄层:\n"
        + "\n".join(f"- {item}" for item in violations)
    )


def test_legacy_global_runtime_and_custom_events_are_removed():
    forbidden = {
        "window.DFI_UI": re.compile(r"\bwindow\s*\.\s*DFI_UI\b"),
        "dfi:pagechange": re.compile(r"""['"]dfi:pagechange['"]"""),
        "dfi:modechange": re.compile(r"""['"]dfi:modechange['"]"""),
    }
    violations = []
    for path in _source_files():
        source = _read(path)
        for label, pattern in forbidden.items():
            if pattern.search(source):
                violations.append(f"{path.relative_to(FRONTEND)}: {label}")

    assert not violations, "P1 禁止保留旧运行时耦合:\n" + "\n".join(
        f"- {item}" for item in violations
    )


def test_fetch_is_centralized_in_api_client():
    allowed = FRONTEND / "api" / "client.js"
    fetch_pattern = re.compile(r"\bfetch\s*\(")
    violations = []
    for path in _source_files():
        if path == allowed:
            continue
        if fetch_pattern.search(_read(path)):
            violations.append(str(path.relative_to(FRONTEND)))

    assert not violations, (
        "业务模块不得自行 fetch，必须通过 api/client.js:\n"
        + "\n".join(f"- {item}" for item in violations)
    )


def test_business_modules_use_domain_apis_not_generic_client():
    violations = []
    business_roots = (FRONTEND / "pages", FRONTEND / "components")
    generic_request = re.compile(r"\bruntime\s*\.\s*api\s*\.\s*request\s*\(")
    for root in business_roots:
        for path in root.rglob("*.js"):
            if generic_request.search(_read(path)):
                violations.append(
                    f"{path.relative_to(FRONTEND)}: runtime.api.request"
                )

    assert not violations, (
        "业务模块不能绕回通用 client:\n"
        + "\n".join(f"- {item}" for item in violations)
    )


def test_frontend_static_import_graph_has_no_cycles():
    files = {path.resolve() for path in _source_files()}
    graph = {path: set() for path in files}
    import_patterns = (
        re.compile(r'''\bfrom\s+["']([^"']+)["']'''),
        re.compile(r'''\bimport\s+["']([^"']+)["']'''),
        re.compile(r'''\bimport\s*\(\s*["']([^"']+)["']\s*\)'''),
    )
    for path in files:
        targets = {
            target
            for pattern in import_patterns
            for target in pattern.findall(_read(path))
        }
        for target in targets:
            if not target.startswith("."):
                continue
            resolved = (path.parent / target).resolve()
            if resolved not in files and not resolved.suffix:
                file_candidate = resolved.with_suffix(".js")
                index_candidate = resolved / "index.js"
                resolved = (
                    file_candidate
                    if file_candidate in files
                    else index_candidate
                )
            if resolved in files:
                graph[path].add(resolved)

    visiting, visited, stack = set(), set(), []
    cycles = []

    def visit(node):
        if node in visiting:
            start = stack.index(node)
            cycles.append(stack[start:] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for dependency in graph[node]:
            visit(dependency)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)

    assert not cycles, "前端静态 import 存在循环:\n" + "\n".join(
        " -> ".join(str(path.relative_to(FRONTEND)) for path in cycle)
        for cycle in cycles
    )


def test_live_and_demo_stores_are_physically_isolated():
    live_path = FRONTEND / "state" / "live-store.js"
    demo_path = FRONTEND / "state" / "demo-store.js"
    assert live_path.is_file() and demo_path.is_file(), (
        "必须分别提供 state/live-store.js 与 state/demo-store.js"
    )

    live_source = _read(live_path)
    demo_source = _read(demo_path)
    assert not re.search(r"(?:demo|mock)[-/_.a-z0-9]*", live_source, re.IGNORECASE), (
        "live-store.js 不得导入或引用 demo/mock 数据"
    )
    assert not re.search(r"(?:live-store|createLiveStore)", demo_source, re.IGNORECASE), (
        "demo-store.js 不得依赖 live store"
    )


def test_demo_data_is_not_injected_into_shared_live_runtime():
    app_source = _read(FRONTEND / "app.js")
    violations = []
    if re.search(r"createUiRuntime\s*\(\s*\{[^}]*\bdemoData\s*:", app_source, re.DOTALL):
        violations.append("app.js: demoData 被注入共享 ui-runtime")
    if re.search(r"\bcontext\s*=\s*\{[^}]*\bdemoData\s*[,}:]", app_source, re.DOTALL):
        violations.append("app.js: demoData 被暴露给共享业务 context")

    live_source = _read(FRONTEND / "state" / "live-store.js")
    if re.search(r"\b(?:demo|mock)\b", live_source, re.IGNORECASE):
        violations.append("state/live-store.js: 引用了 demo/mock")

    assert not violations, (
        "demo/live 必须在运行时隔离，演示数据不能预注入真实运行时:\n"
        + "\n".join(f"- {item}" for item in violations)
    )


def test_project_switch_has_race_guard_and_atomic_derived_state_reset():
    sources = {
        path: _read(path)
        for path in (FRONTEND / "pages").rglob("*.js")
    }
    combined = "\n".join(sources.values())

    has_abort_guard = (
        "AbortController" in combined
        and re.search(r"\.abort\s*\(", combined)
        and re.search(r"\bsignal\b", combined)
    )
    has_generation_guard = (
        re.search(r"\b(?:request|load|project)(?:Generation|Epoch|Token)\b", combined, re.IGNORECASE)
        and re.search(r"(?:\+\+|!==|!=)", combined)
    )
    assert has_abort_guard or has_generation_guard, (
        "项目数据加载缺少竞态防护；必须使用 AbortController，"
        "或请求 generation/epoch 校验，防止旧项目响应覆盖新项目"
    )

    reset_keys = ("table", "leftVersion", "rightVersion", "focus")
    switch_blocks = re.findall(
        r"(?:selectProject|switchProject|projectSelect)[\s\S]{0,1200}",
        combined,
        re.IGNORECASE,
    )
    reset_scope = "\n".join(switch_blocks)
    missing = [
        key for key in reset_keys
        if not re.search(
            rf"\b{key}\b\s*:\s*(?:null|undefined|\[\]|\{{\}})",
            reset_scope,
        )
    ]
    assert not missing, (
        "项目切换必须原子清空派生路由/选择状态，当前缺少: "
        + ", ".join(missing)
    )
