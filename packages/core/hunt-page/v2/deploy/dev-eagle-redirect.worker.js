// dev.eagle.utopiamodels.ai: the old preview host. Eagle Eye's dev server is now Ra (tailnet :8450) and the promoted
// build is eagle.utopiamodels.ai, so the old dev hostname redirects there, path and query kept.
export default {
  fetch(req) {
    const u = new URL(req.url);
    return Response.redirect("https://eagle.utopiamodels.ai" + u.pathname + u.search, 302);
  },
};
