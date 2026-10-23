import uvicorn

if __name__ == "__main__":
    print("=" * 65)
    print(" RouteOpt: Commercial Fleet & AI Dispatch System")
    print(" Server URL: http://127.0.0.1:8000")
    print(" API Documentation: http://127.0.0.1:8000/docs")
    print("=" * 65)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
