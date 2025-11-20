# 调试 Warning 日志不显示的问题

## 问题描述

您报告说 `logger.warning()` 日志没有打印，但是能看到 `info` 级别的日志。

## 诊断结果

我已经运行了诊断测试，结果显示：

✅ **日志系统本身工作正常** - warning 日志可以正常输出
✅ **日志级别配置正确** - Root logger 级别是 INFO，可以输出 WARNING
✅ **JSON 和 Console 格式都正常** - 两种输出格式都能正确显示 warning

**结论：问题不在日志系统，而是您的 HTTP 异常处理器可能没有被触发！**

## 可能的原因

1. **异常处理器没有被调用** - HTTP 异常可能在其他地方被捕获了
2. **请求没有产生 HTTP 异常** - 您访问的端点可能没有抛出异常
3. **Uvicorn 日志配置覆盖** - Uvicorn 启动时可能重新配置了日志系统

## 调试步骤

### 步骤 1: 验证日志系统工作正常

运行诊断脚本：

```bash
python3 test_warning_logs.py
```

您应该看到 warning 日志正常输出。如果看不到，说明日志系统有问题。

### 步骤 2: 添加调试代码验证处理器是否被调用

我已经在 `src/rag_service/main.py` 的 HTTP 异常处理器中添加了调试代码：

```python
async def _http_exception_handler(request: Request, exc):
    # DEBUG: Print to console to verify handler is called
    print(f"[DEBUG] HTTP exception handler called! Exception type: {type(exc).__name__}")
    
    # ... existing code ...
    
    print(f"[DEBUG] About to log warning: status_code={status_code}, detail={detail}")
    logger.warning("HTTP exception occurred", ...)
    print(f"[DEBUG] Warning logged successfully")
```

### 步骤 3: 启动应用并触发异常

1. 启动应用：

```bash
poetry run uvicorn src.rag_service.main:app --reload
```

2. 在另一个终端运行测试脚本：

```bash
python3 test_http_exception.py
```

### 步骤 4: 检查服务器控制台输出

在服务器控制台中查找：

1. **[DEBUG] 消息** - 如果看到这些消息，说明处理器被调用了
2. **warning 日志** - 应该在 [DEBUG] 消息之间看到 warning 日志

## 可能的情况和解决方案

### 情况 1: 看到 [DEBUG] 但没有 warning 日志

**原因：** Uvicorn 的日志配置覆盖了我们的配置

**解决方案：** 在启动 uvicorn 时禁用其日志配置：

```python
# 在 main.py 的 if __name__ == "__main__": 部分
uvicorn.run(
    "src.rag_service.main:app",
    host=settings.host,
    port=settings.port,
    reload=settings.debug,
    log_config=None,  # 添加这一行，禁用 uvicorn 的日志配置
)
```

或者在启动后重新配置日志：

```python
# 在 lifespan 函数的 startup 部分
from .logging_config import configure_logging
configure_logging(log_level="INFO", json_output=False, force_reconfigure=True)
```

### 情况 2: 没有看到任何 [DEBUG] 消息

**原因：** 异常处理器根本没有被调用

**可能的子原因：**

1. **异常在中间件中被捕获** - 检查是否有其他中间件捕获了异常
2. **路由不存在** - FastAPI 可能返回默认的 404 响应而不是抛出异常
3. **异常处理器注册失败** - 检查 `setup_exception_handlers(app)` 是否被调用

**解决方案：** 在 `setup_exception_handlers` 函数开始处添加日志：

```python
def setup_exception_handlers(app: FastAPI) -> None:
    print("[DEBUG] Setting up exception handlers...")
    logger.info("Registering exception handlers")
    # ... rest of the code
```

### 情况 3: 看到 [DEBUG] 和 warning 日志

**恭喜！** 日志系统工作正常。之前可能是：
- 您访问的端点没有触发异常
- 或者您在错误的地方查找日志

## 常见问题

### Q: 为什么 INFO 日志能看到，WARNING 看不到？

A: 这种情况通常不是日志级别的问题（因为 WARNING > INFO），而是：
- 代码路径问题：warning 日志所在的代码没有被执行
- 日志输出位置问题：warning 日志可能输出到了不同的地方（文件 vs 控制台）

### Q: 如何确保日志配置不被覆盖？

A: 在 uvicorn 启动后强制重新配置：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from .logging_config import configure_logging
    configure_logging(log_level="INFO", json_output=False, force_reconfigure=True)
    logger.info("Logging reconfigured after uvicorn startup")
    # ... rest of startup code
```

### Q: 如何查看所有日志配置？

A: 运行诊断脚本的 Test 4 和 Test 5：

```bash
python3 test_warning_logs.py
```

查看 "Root Logger Level" 和 "Specific Logger Level" 部分。

## 下一步

1. 运行 `python3 test_warning_logs.py` 验证日志系统
2. 启动应用并运行 `python3 test_http_exception.py`
3. 检查服务器控制台输出
4. 根据上面的情况选择对应的解决方案

## 清理调试代码

当问题解决后，记得删除 `main.py` 中的 `print()` 调试语句。

