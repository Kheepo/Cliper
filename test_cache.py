import sys
sys.path.append('api')
import asyncio
from middleware.performance import cache

async def test_cache():
    print("Testing cache functionality...")
    
    # Test set and get
    await cache.set('test_key', 'test_value', 60)
    result = await cache.get('test_key')
    print(f'Cache test - Set and get result: {result}')
    
    # Test cache miss
    miss_result = await cache.get('nonexistent_key')
    print(f'Cache miss test result: {miss_result}')
    
    # Show stats
    print(f'Cache stats after test: {cache.get_stats()}')

if __name__ == '__main__':
    asyncio.run(test_cache())