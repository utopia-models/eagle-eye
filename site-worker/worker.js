// eagleeye.sh on Cloudflare Workers (utopia-models/knowledge#19515): site/ as static assets, plus the redirects,
// proxied paths and headers the site needs.
const INSTALL = 'https://raw.githubusercontent.com/utopia-models/eagle-eye/main/install.sh';
const DEMO = 'https://utopia-models.github.io/eagle-eye/';

function withHeaders(res, pathname) {
  const out = new Response(res.body, res);
  out.headers.set('X-Content-Type-Options', 'nosniff');
  out.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  if (/^\/(assets|vendor|fonts)\//.test(pathname)) out.headers.set('Cache-Control', 'public, max-age=604800');
  if (pathname.startsWith('/.well-known/')) {
    out.headers.set('Content-Type', 'application/json');
    out.headers.set('Cache-Control', 'public, max-age=3600');
  }
  return out;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;
    if (url.hostname === 'www.eagleeye.sh') {
      return Response.redirect(`https://eagleeye.sh${pathname}${url.search}`, 308);
    }
    if (pathname === '/demo') return Response.redirect(new URL('/demo/', url).href, 307);
    if (pathname.startsWith('/p/') && pathname.slice(3) && !pathname.slice(3).includes('/')) {
      return Response.redirect(`https://eagle.utopiamodels.ai${pathname}${url.search}`, 307);
    }
    if (pathname === '/install' || pathname === '/install.sh') {
      return withHeaders(await fetch(INSTALL), pathname);
    }
    if (pathname.startsWith('/demo/')) {
      // Concatenated, not resolved: a path such as /demo//host must stay under DEMO.
      return withHeaders(await fetch(DEMO + pathname.slice('/demo/'.length) + url.search), pathname);
    }
    return withHeaders(await env.ASSETS.fetch(request), pathname);
  },
};
