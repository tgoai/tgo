// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { locales, defaultLanguage } from "@/lib/i18n";


export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. 检查路径是否已经包含语言前缀 (例如 /zh/about 或 /en/contact)
  // 注意：需要排除静态资源 (如 .ico, .png, .css 等) 和 API 路由
  const pathnameHasLocale = locales.some(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`
  );

  // 2. 如果路径没有语言前缀，且不是静态资源
  if (!pathnameHasLocale) {
    // 构造新的 URL，将默认语言前缀添加到路径开头
    const newPathname = `/${defaultLanguage}${pathname}`;
    // 执行重定向
    return NextResponse.redirect(new URL(newPathname, request.url));
  }

  return NextResponse.next();
}

// 配置 matcher，让 middleware 只处理特定路径
// 这里排除了静态文件和 api 路由，只处理页面路由
export const config = {
  matcher: [
    /*
     * 匹配所有路径，除了:
     * - _next/static (静态文件)
     * - _next/image (图片优化)
     * - favicon.ico (图标)
     * - 公共文件 (public folder)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};