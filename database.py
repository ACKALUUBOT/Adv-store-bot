from motor.motor_asyncio import AsyncIOMotorClient
import config

# Async MongoDB Client Setup using Motor
client = AsyncIOMotorClient(config.MONGO_URI)
db = client['sub_management']

# Collections
channels_col = db['channels']
users_col = db['users']
utr_col = db['verified_utrs']


async def init_db():
    """
    सर्च और डेटाबेस ऑपरेशन्स को तेज़ करने और डुप्लिकेट डेटा रोकने के लिए ऑटो-इंडेक्सिंग
    """
    try:
        # Users Index
        await users_col.create_index("user_id", unique=True)
        
        # Channels / Inventory Indexes
        await channels_col.create_index("item_id", unique=True, sparse=True)
        await channels_col.create_index("category")
        
        # Verified UTR Index (Duplicate Payment Check)
        await utr_col.create_index("utr", unique=True)
        
        print("Database Indexes initialized successfully.")
    except Exception as e:
        print(f"Error initializing DB indexes: {e}")
      
