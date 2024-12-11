import os
import redis.asyncio as redis
from kombu.utils.url import safequote
from redis.exceptions import ConnectionError, TimeoutError
import asyncio

# Read Redis host and port from environment variables with defaults
redis_host = safequote(os.environ.get('REDIS_HOST', 'localhost'))
redis_port = int(os.environ.get('REDIS_PORT', 6379))  # Default to 6379
redis_db = int(os.environ.get('REDIS_DB', 0))  # Default database 0

# Create Redis client
redis_client = None

async def create_redis_client():
    global redis_client
    try:
        redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        # Test connection asynchronously
        await redis_client.ping()  # Ping the server to ensure it's reachable
        print(f"Connected to Redis at {redis_host}:{redis_port}")
    except (ConnectionError, TimeoutError) as e:
        print(f"Error: Unable to connect to Redis at {redis_host}:{redis_port}. Details: {e}")
        redis_client = None  # Fallback to None if connection fails

# Functions for Redis operations
async def add_key_value_redis(key, value, expire=None):
    if redis_client:
        try:
            await redis_client.set(key, value)
            if expire:
                await redis_client.expire(key, expire)
        except (ConnectionError, TimeoutError) as e:
            print(f"Error: Unable to set key '{key}' in Redis. Details: {e}")
    else:
        print("Error: Redis client is not connected.")

async def get_value_redis(key):
    if redis_client:
        try:
            return await redis_client.get(key)
        except (ConnectionError, TimeoutError) as e:
            print(f"Error: Unable to get key '{key}' from Redis. Details: {e}")
            return None
    else:
        print("Error: Redis client is not connected.")
        return None

async def delete_key_redis(key):
    if redis_client:
        try:
            await redis_client.delete(key)
        except (ConnectionError, TimeoutError) as e:
            print(f"Error: Unable to delete key '{key}' from Redis. Details: {e}")
    else:
        print("Error: Redis client is not connected.")

# Example of using this client setup
async def main():
    await create_redis_client()
    if redis_client:
        await add_key_value_redis("test_key", "test_value")
        value = await get_value_redis("test_key")
        print(f"Retrieved value: {value}")
        await delete_key_redis("test_key")
    else:
        print("Redis client failed to initialize.")

# Run the example (in real applications, this will be triggered by your app logic)
if __name__ == "__main__":
    asyncio.run(main())
