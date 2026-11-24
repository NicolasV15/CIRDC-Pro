/* Fixtures written for the former IEEE home page answer the unified home search through their own `/api/papers` route,
 * and report no arXiv papers. Register after the fixture's catch-all route: later routes run first. */
exports.serveUnifiedFromLegacy=async function(context){
 await context.route(url=>url.pathname==='/api/search/unified'||url.pathname==='/api/arxiv/overview',route=>{
  const u=new URL(route.request().url());
  if(u.pathname==='/api/arxiv/overview')return route.fulfill({json:{indexed:0,year_range:null}});
  u.pathname='/api/papers';u.searchParams.delete('sources');
  return route.fallback({url:u.toString()});
 });
};
