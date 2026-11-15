import { NextResponse, type NextRequest } from 'next/server';

// Next decodes route params before Server Components receive them. Reject encoded
// promotion keys here so alternate encodings cannot resolve as canonical identities.
export function middleware(request: NextRequest) {
  const pathname = request.url.split('?')[0];
  const routePart = pathname.slice(pathname.indexOf('/promotions/') + '/promotions/'.length);
  if (routePart.includes('%')) {
    return new NextResponse(
      '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Promotion not found</title></head><body><main id="main-content"><h1>Promotion not found</h1><p>This promotion is unavailable.</p><a href="/check">Check my purchase</a> · <a href="/">Home</a></main></body></html>',
      { status: 404, headers: { 'content-type': 'text/html; charset=utf-8' } },
    );
  }
  return NextResponse.next();
}

export const config = { matcher: ['/promotions/:path*'] };
