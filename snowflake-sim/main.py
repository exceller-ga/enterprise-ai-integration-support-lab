import asyncio

from fastapi import FastAPI, HTTPException


app = FastAPI(
    title="Snowflake Simulator"
)


@app.get("/health")
async def health():
    return {
        "service": "snowflake-sim",
        "status": "ok"
    }


@app.get("/query")
async def query(
    mode: str = "normal"
):

    if mode == "normal":

        delay = 0.1

    elif mode == "slow":

        delay = 2.0

    elif mode == "timeout":

        delay = 10.0

    else:

        raise HTTPException(
            status_code=400,
            detail="Unknown Snowflake simulation mode"
        )

    await asyncio.sleep(delay)

    return {
        "service": "snowflake-sim",
        "mode": mode,
        "simulated_delay_seconds": delay,
        "rows": [
            {
                "category": "platform incidents",
                "count": 4
            },
            {
                "category": "identity incidents",
                "count": 2
            }
        ]
    }
