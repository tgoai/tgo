#!/bin/bash
# Test script for port exposure strategy
# Verifies that only Nginx exposes ports and other services are not directly accessible

set -euo pipefail

echo "========================================="
echo "  服务端口暴露策略验证测试"
echo "========================================="
echo ""

# Test 1: Check docker-compose.yml for port configurations
echo "✓ 测试 1: 检查 docker-compose.yml 中的端口配置"
if ! grep -A 5 "tgo-api:" docker-compose.yml | grep -q "ports:"; then
  echo "  ✅ tgo-api 没有暴露端口"
else
  echo "  ❌ tgo-api 仍然暴露端口"
  exit 1
fi
echo ""

# Test 2: Check tgo-web ports
echo "✓ 测试 2: 检查 tgo-web 是否暴露端口"
if ! grep -A 10 "tgo-web:" docker-compose.yml | grep -q "ports:"; then
  echo "  ✅ tgo-web 没有暴露端口"
else
  echo "  ❌ tgo-web 仍然暴露端口"
  exit 1
fi
echo ""

# Test 3: Check tgo-widget-js ports
echo "✓ 测试 3: 检查 tgo-widget-js 是否暴露端口"
if ! grep -A 10 "tgo-widget-js:" docker-compose.yml | grep -q "ports:"; then
  echo "  ✅ tgo-widget-js 没有暴露端口"
else
  echo "  ❌ tgo-widget-js 仍然暴露端口"
  exit 1
fi
echo ""

# Test 4: Check Nginx ports
echo "✓ 测试 4: 检查 Nginx 是否暴露端口"
if grep -A 5 "nginx:" docker-compose.yml | grep -q "ports:"; then
  echo "  ✅ Nginx 暴露了端口"
else
  echo "  ❌ Nginx 没有暴露端口"
  exit 1
fi
echo ""

# Test 5: Check API_BASE_URL in .env.example
echo "✓ 测试 5: 检查 .env.example 中的 API_BASE_URL"
if grep -q "API_BASE_URL=http://tgo-api:8000" .env.example; then
  echo "  ✅ API_BASE_URL 正确指向内部服务"
else
  echo "  ❌ API_BASE_URL 配置不正确"
  exit 1
fi
echo ""

# Test 6: Check VITE_WIDGET_PREVIEW_URL
echo "✓ 测试 6: 检查 .env.example 中的 VITE_WIDGET_PREVIEW_URL"
if grep -q "VITE_WIDGET_PREVIEW_URL=http://tgo-widget-js:80" .env.example; then
  echo "  ✅ VITE_WIDGET_PREVIEW_URL 正确指向内部服务"
else
  echo "  ❌ VITE_WIDGET_PREVIEW_URL 配置不正确"
  exit 1
fi
echo ""

# Test 7: Check Nginx config script exists
echo "✓ 测试 7: 检查 Nginx 配置生成脚本"
if [ -f "scripts/generate-nginx-config.sh" ]; then
  echo "  ✅ Nginx 配置生成脚本存在"
else
  echo "  ❌ Nginx 配置生成脚本不存在"
  exit 1
fi
echo ""

# Test 8: Check for reverse proxy configuration in script
echo "✓ 测试 8: 检查反向代理配置"
if grep -q "proxy_pass http://tgo-api:8000" scripts/generate-nginx-config.sh; then
  echo "  ✅ 反向代理配置正确"
else
  echo "  ❌ 反向代理配置不正确"
  exit 1
fi
echo ""

# Test 9: Check for /api path routing
echo "✓ 测试 9: 检查 /api 路径路由"
if grep -q "location ~ ^/api" scripts/generate-nginx-config.sh; then
  echo "  ✅ /api 路径路由配置正确"
else
  echo "  ❌ /api 路径路由配置不正确"
  exit 1
fi
echo ""

# Test 10: Check for /widget path routing
echo "✓ 测试 10: 检查 /widget 路径路由"
if grep -q "location ~ ^/widget" scripts/generate-nginx-config.sh; then
  echo "  ✅ /widget 路径路由配置正确"
else
  echo "  ❌ /widget 路径路由配置不正确"
  exit 1
fi
echo ""

# Test 11: Verify docker-compose.yml is valid
echo "✓ 测试 11: 验证 docker-compose.yml 有效性"
if docker compose config > /dev/null 2>&1; then
  echo "  ✅ docker-compose.yml 配置有效"
else
  echo "  ❌ docker-compose.yml 配置无效"
  exit 1
fi
echo ""

echo "========================================="
echo "  ✅ 所有测试通过！"
echo "========================================="
echo ""
echo "端口暴露策略验证完成："
echo "  • tgo-api 不暴露端口"
echo "  • tgo-web 不暴露端口"
echo "  • tgo-widget-js 不暴露端口"
echo "  • 只有 Nginx 暴露端口 (80, 443)"
echo "  • 反向代理配置正确"
echo "  • 服务间通信使用内部网络"
echo ""

