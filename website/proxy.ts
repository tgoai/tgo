import { createI18nMiddleware } from "fumadocs-core/i18n/middleware";
import { i18n, locales, defaultLanguage } from "@/lib/i18n";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 根路径重定向
  if (pathname === "/") {
    // 可选：根据 Accept-Language 头判断用户偏好语言
    const preferredLocale = defaultLanguage; // 默认中文
    return NextResponse.redirect(new URL(`/${preferredLocale}`, request.url));
  }

  // 防止访问不带语言前缀的路径
  const pathnameHasLocale = locales.some(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`,
  );

  if (!pathnameHasLocale) {
    return NextResponse.redirect(
      new URL(`/${defaultLanguage}${pathname}`, request.url),
    );
  }

  return NextResponse.next();
}

export default createI18nMiddleware(i18n);

export const config = {
  // Matcher ignoring `/_next/` and `/api/`
  // You may need to adjust it to ignore static assets in `/public` folder
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
