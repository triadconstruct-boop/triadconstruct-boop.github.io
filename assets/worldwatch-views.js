/* Presentation only: geographic selection never changes evidence or scores. */
((root, factory) => {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.WorldwatchViews = api;
})(globalThis, () => {
  "use strict";

  function balancedOverview(claims, regions, limit = 24) {
    const buckets = new Map(regions.map(region => [region.id, []]));
    claims.forEach(claim => {
      const id = claim.worldwatch?.primary_region || "global";
      if (!buckets.has(id)) buckets.set(id, []);
      buckets.get(id).push(claim);
    });
    // Rotate topics within each region, with original priority retained inside
    // each topic. This gives the overview more than repeated military updates.
    const queues = [...buckets.values()].filter(rows => rows.length).map(rows => {
      const topics = new Map();
      rows.forEach(claim => {
        const key = claim.worldwatch?.conflicts?.[0] || claim.domains?.[0] || "SECURITY";
        if (!topics.has(key)) topics.set(key, []);
        topics.get(key).push(claim);
      });
      const queue = [];
      while ([...topics.values()].some(topic => topic.length)) {
        topics.forEach(topic => { if (topic.length) queue.push(topic.shift()); });
      }
      return queue;
    });
    const result = [];
    while (result.length < limit && queues.some(queue => queue.length)) {
      for (const queue of queues) {
        if (queue.length && result.length < limit) result.push(queue.shift());
      }
    }
    return result;
  }

  function selectClaims(claims, regions, {region = "overview", conflict = "all", state = "ALL", limit = 24} = {}) {
    const matching = claims.filter(claim =>
      (state === "ALL" || claim.state === state) &&
      (["overview", "all"].includes(region) || claim.worldwatch?.regions?.includes(region)) &&
      (conflict === "all" || claim.worldwatch?.conflicts?.includes(conflict))
    );
    return region === "overview" && conflict === "all" ? balancedOverview(matching, regions, limit) : matching;
  }

  return {balancedOverview, selectClaims};
});
