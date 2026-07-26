import { createEventScope } from "./event-scope.js";

export function bindAssistantEvents(ctx) {
  const { $ } = ctx;
  const scope = createEventScope();

  scope.assign($("sendChat"), "onclick", () => {
    const input = $("chatInput");
    const value = input.value.trim();
    if (!value) return;
    input.value = "";
    ctx.ask(value);
  });
  scope.assign($("chatInput"), "onkeydown", event => {
    if (event.key === "Enter") $("sendChat").click();
  });
  document.querySelectorAll(".suggestion").forEach(item => {
    scope.assign(item, "onclick", () => ctx.ask(item.textContent.trim()));
  });
  return () => scope.cleanup();
}
