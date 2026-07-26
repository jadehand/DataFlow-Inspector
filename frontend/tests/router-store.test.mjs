import assert from "node:assert/strict";
import test from "node:test";

import { createRouter, readRoute } from "../src/router.js";
import { createDemoStore } from "../src/state/demo-store.js";
import { createLiveStore } from "../src/state/live-store.js";
import { createStore } from "../src/state/store.js";


function createFakeWindow(href) {
  const listeners = new Map();
  const windowObject = {
    location: new URL(href),
    history: {
      pushState(_state, _unused, next) {
        windowObject.location = new URL(next);
      },
      replaceState(_state, _unused, next) {
        windowObject.location = new URL(next);
      }
    },
    addEventListener(name, listener) {
      listeners.set(name, listener);
    },
    removeEventListener(name) {
      listeners.delete(name);
    }
  };
  windowObject.dispatch = name => listeners.get(name)?.({ type: name });
  return windowObject;
}


test("router encodes and decodes a complete deep link", () => {
  const store = createStore({ activePage: "overview" });
  const windowObject = createFakeWindow("http://example.test/app");
  const router = createRouter({ store, windowObject });

  router.navigate("lineage", {
    projectId: "project / 42",
    table: "dws.token_minute",
    leftVersion: 3,
    rightVersion: 8,
    focus: "column:user_id"
  });

  assert.deepEqual(readRoute(windowObject.location), {
    activePage: "lineage",
    projectId: "project / 42",
    table: "dws.token_minute",
    leftVersion: "3",
    rightVersion: "8",
    focus: "column:user_id"
  });
  router.destroy();
});


test("router supplies a safe default and ignores unknown fields", () => {
  assert.deepEqual(
    readRoute(new URL("http://example.test/app?unknown=value")),
    {
      activePage: "overview",
      projectId: null,
      table: null,
      leftVersion: null,
      rightVersion: null,
      focus: null
    }
  );
});


test("router restores the complete application route on popstate", () => {
  const store = createStore({
    activePage: "overview",
    projectId: null,
    table: null,
    leftVersion: null,
    rightVersion: null,
    focus: null
  });
  const windowObject = createFakeWindow(
    "http://example.test/app?page=detail&project=p1&table=ods.user"
  );
  const router = createRouter({ store, windowObject });
  const observations = [];
  const unsubscribe = store.subscribe(state => observations.push(state));

  router.start();
  assert.deepEqual(
    {
      activePage: store.getState().activePage,
      projectId: store.getState().projectId,
      table: store.getState().table
    },
    { activePage: "detail", projectId: "p1", table: "ods.user" }
  );

  windowObject.location = new URL(
    "http://example.test/app?page=compare&project=p2&table=dws.order"
    + "&left=11&right=14&focus=column%3Aorder_id"
  );
  windowObject.dispatch("popstate");

  assert.deepEqual(store.getState(), {
    activePage: "compare",
    projectId: "p2",
    table: "dws.order",
    leftVersion: "11",
    rightVersion: "14",
    focus: "column:order_id"
  });
  assert.equal(observations.at(-1).projectId, "p2");

  unsubscribe();
  router.destroy();
});


test("store updates produce deeply immutable snapshots", () => {
  const initial = {
    activePage: "overview",
    nested: { count: 1, rows: [{ name: "first" }] }
  };
  const store = createStore(initial);
  const before = store.getState();
  let observed;
  const unsubscribe = store.subscribe(state => {
    observed = state;
  });

  store.setState({ activePage: "assets" });
  const after = store.getState();

  assert.notStrictEqual(after, before);
  assert.deepEqual(before, initial);
  assert.equal(after.activePage, "assets");
  assert.strictEqual(observed, after);
  assert.throws(() => {
    after.activePage = "impact";
  }, TypeError);
  assert.throws(() => {
    after.nested.count = 2;
  }, TypeError);
  assert.throws(() => {
    after.nested.rows.push({ name: "second" });
  }, TypeError);
  assert.throws(() => {
    after.nested.rows[0].name = "mutated";
  }, TypeError);
  assert.equal(store.getState().nested.rows[0].name, "first");

  unsubscribe();
});


test("live and demo stores have isolated state and capabilities", () => {
  const live = createLiveStore();
  const demo = createDemoStore({ tables: [{ name: "demo_table" }] });

  assert.notStrictEqual(live, demo);
  assert.notStrictEqual(live.getSnapshot(), demo.getSnapshot());

  live.replace({ tables: [{ name: "live_table" }] });
  assert.deepEqual(live.getSnapshot().tables, [{ name: "live_table" }]);
  assert.deepEqual(demo.getSnapshot().tables, [{ name: "demo_table" }]);

  const leakedDemoSnapshot = demo.getSnapshot();
  leakedDemoSnapshot.tables[0].name = "mutated";
  assert.equal(demo.getSnapshot().tables[0].name, "demo_table");
  assert.equal("demoData" in live.getSnapshot(), false);
  assert.equal("mockData" in live.getSnapshot(), false);

  const leakedLiveSnapshot = live.getSnapshot();
  assert.throws(() => {
    leakedLiveSnapshot.tables.push({ name: "leaked" });
  }, TypeError);
  assert.throws(() => {
    leakedLiveSnapshot.tables[0].name = "mutated";
  }, TypeError);
  assert.deepEqual(live.getSnapshot().tables, [{ name: "live_table" }]);

  demo.reset();
  assert.deepEqual(demo.getSnapshot().tables, [{ name: "demo_table" }]);
});
