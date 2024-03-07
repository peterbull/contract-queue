from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"Hello": "Claudio", "Hi There": "Rosie"}
