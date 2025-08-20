import os
import uvicorn


if __name__ == "__main__":
    os.environ.setdefault("GPIOZERO_PIN_FACTORY", "pigpio")
    uvicorn.run(
        "asgi:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )
