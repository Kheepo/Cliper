import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.database import get_db
from api.database.models import User, Clip
from api.routers.analytics import _get_user_analytics
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import traceback

async def debug_analytics():
    """Debug the analytics function to see what's causing the 500 error"""
    
    # Get database session
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        # Test user ID from our JWT token
        test_user_id = "8cfab4fc-a2a7-4ba2-9f8e-eee314c9946"
        
        print(f"Testing analytics for user ID: {test_user_id}")
        
        # Check if user exists
        user = db.query(User).filter(User.id == test_user_id).first()
        if user:
            print(f"✓ User found: {user.email}")
        else:
            print("✗ User not found in database")
            # Let's see what users exist
            users = db.query(User).all()
            print(f"Available users: {[u.id for u in users]}")
            return
        
        # Check clips for this user
        clips = db.query(Clip).filter(Clip.user_id == test_user_id).all()
        print(f"User has {len(clips)} clips")
        
        # Test the analytics function
        print("\nTesting _get_user_analytics function...")
        
        # Calculate time range (1 day)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        
        result = await _get_user_analytics(
            user_id=test_user_id,
            start_time=start_time,
            end_time=end_time,
            db=db
        )
        
        print("✓ Analytics function completed successfully")
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"✗ Error in analytics function: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        print("Traceback:")
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(debug_analytics())