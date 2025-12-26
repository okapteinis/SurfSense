# PHASE 1: Foundation - Design & Architecture

**Status:** IN PROGRESS
**Date Started:** 2025-12-26
**Objective:** Complete architecture design before implementation

---

## Part 1: Upstream Checkpointer Review

### What We Learned from Upstream

**Upstream Implementation (MODSetter/SurfSense):**
```
File: app/agents/new_chat/checkpointer.py (94 lines)
Tech: LangGraph AsyncPostgresSaver
Pattern: Lazy initialization with global instance
```

**Key Components:**
1. `get_postgres_connection_string()` - Converts asyncpg URL to psycopg3
2. `get_checkpointer()` - Creates/returns checkpointer instance
3. `setup_checkpointer_tables()` - Creates schema on startup
4. `close_checkpointer()` - Cleanup on shutdown

**Dependencies:**
- `langgraph` (already in pyproject.toml)
- `langgraph-checkpoint-postgres` (may need adding)
- `psycopg` (PostgreSQL async driver)
- `asyncpg` (already present)

### Why Checkpointing Matters

- **Problem:** Chat history/conversation state lost on restart
- **Solution:** Persist to PostgreSQL using LangGraph checkpointer
- **Benefit:** Message history survives app restarts, better UX

---

## Part 2: Your Architecture Design

### Design Decisions

✅ **Use LangGraph's AsyncPostgresSaver** (proven, maintained by LangGraph)
✅ **Keep your SQLAlchemy async patterns** (consistency)
✅ **Your database schema integration** (not copy upstream)
✅ **Proper error handling & logging** (robustness)
✅ **Configurable via environment** (flexibility)

### Proposed Module Structure

```
surfsense_backend/app/
├── services/
│   └── persistence/
│       ├── __init__.py
│       ├── message_checkpointer.py    (NEW)
│       ├── storage_adapter.py         (NEW)
│       └── migrations.py              (NEW)
├── config/
│   └── persistence.py                 (NEW)
└── alembic/
    └── versions/
        └── 20251226_add_checkpointer_tables.py (NEW)
```

### File 1: `app/config/persistence.py`

**Purpose:** Configuration for persistence layer

```python
from pydantic import BaseSettings
from functools import lru_cache

class PersistenceConfig(BaseSettings):
    # Checkpointer settings
    enable_checkpointing: bool = True
    checkpointer_cleanup_timeout: int = 5  # seconds
    
    # Message settings
    max_checkpoint_history: int = 1000  # Keep last N checkpoints
    checkpoint_cleanup_interval: int = 3600  # seconds
    
    class Config:
        env_prefix = "PERSISTENCE_"
        case_sensitive = False

@lru_cache()
def get_persistence_config() -> PersistenceConfig:
    return PersistenceConfig()
```

### File 2: `app/services/persistence/message_checkpointer.py`

**Purpose:** Checkpointer service (your implementation)

```python
# Key responsibilities:
# 1. Initialize AsyncPostgresSaver from config.DATABASE_URL
# 2. Create tables on startup (setup_checkpointer_tables)
# 3. Provide get_checkpointer() for agents to use
# 4. Cleanup on shutdown (close_checkpointer)
# 5. Error handling & logging
# 6. Connection management

# Structure:
class MessageCheckpointer:
    """Wrapper around LangGraph's AsyncPostgresSaver"""
    
    def __init__(self, db_url: str, config: PersistenceConfig)
    async def initialize()
    async def get_saver()
    async def setup_tables()
    async def cleanup()
    async def get_checkpoint(checkpoint_id: str)
    async def list_checkpoints(limit: int)
    async def delete_old_checkpoints(days: int)

# Global instance management (similar to upstream)
_checkpointer: MessageCheckpointer | None = None

async def get_checkpointer() -> AsyncPostgresSaver
async def setup_checkpointer_tables() -> None
async def close_checkpointer() -> None
```

### File 3: `app/services/persistence/storage_adapter.py`

**Purpose:** Bridge between your app and checkpointer

```python
# Responsibilities:
# 1. Save message to database
# 2. Save agent state to checkpointer
# 3. Retrieve conversation history
# 4. Handle errors gracefully

class ConversationStorage:
    """Handles persistence of conversations"""
    
    async def save_message(
        conversation_id: str,
        message: ChatMessage,
        checkpoint_id: str
    ) -> None
    
    async def get_conversation_history(
        conversation_id: str,
        limit: int = 50
    ) -> List[ChatMessage]
    
    async def save_agent_state(
        conversation_id: str,
        state: dict,
        checkpoint_id: str
    ) -> None
    
    async def restore_agent_state(
        conversation_id: str,
        checkpoint_id: str
    ) -> dict
```

### File 4: Database Migration

**File:** `alembic/versions/20251226_add_checkpointer_tables.py`

```python
# Migration creates tables needed by LangGraph checkpointer:
# - checkpoint (stores agent state snapshots)
# - checkpoint_write (write operations)
# - checkpoint_blobs (large data blobs)
# - checkpoint_pendingwrites (pending operations)

def upgrade():
    # Create checkpointer tables
    # These are created automatically by AsyncPostgresSaver.setup()
    # But we can add our own columns for tracking:
    # - conversation_id (FK to conversations)
    # - created_at (timestamp)
    # - archived (soft delete)
    pass

def downgrade():
    # Drop tables
    pass
```

---

## Part 3: Integration Points

### Update `app/app.py` Lifespan

```python
from app.services.persistence import (
    setup_checkpointer_tables,
    close_checkpointer,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing persistence layer...")
    await setup_checkpointer_tables()
    logger.info("Checkpointer ready")
    
    yield
    
    # Shutdown
    logger.info("Closing persistence connections...")
    await close_checkpointer()
    logger.info("Persistence layer shutdown complete")
```

### Update Agent Initialization

```python
# In your agent/chat handlers:
from app.services.persistence import get_checkpointer

checkpointer = await get_checkpointer()

# Pass to LangGraph graph:
app_with_checkpointer = graph.compile(checkpointer=checkpointer)
```

### Update Chat Routes

```python
# In app/routes/chats_routes.py:
from app.services.persistence import ConversationStorage

storage = ConversationStorage()

# On each message:
await storage.save_message(
    conversation_id=chat.id,
    message=user_message,
    checkpoint_id=checkpoint_id
)

# On retrieve history:
history = await storage.get_conversation_history(chat.id)
```

---

## Part 4: Database Schema

### Checkpointer Tables (Auto-created by LangGraph)

```sql
-- Created by AsyncPostgresSaver.setup()
CREATE TABLE IF NOT EXISTS checkpoint (
    thread_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT "",
    created_at BIGINT NOT NULL,
    metadata JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT "",
    blob_id TEXT NOT NULL,
    data BYTEA NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, blob_id)
);
```

### Custom Columns (Your additions)

```sql
ALTER TABLE checkpoint ADD COLUMN conversation_id UUID REFERENCES conversations(id);
ALTER TABLE checkpoint ADD COLUMN user_id UUID REFERENCES users(id);
ALTER TABLE checkpoint ADD COLUMN archived BOOLEAN DEFAULT FALSE;
CREATE INDEX idx_checkpoint_conversation ON checkpoint(conversation_id);
```

---

## Part 5: Error Handling Strategy

### Scenarios to Handle

1. **Database Connection Failure**
   - Retry with exponential backoff
   - Fall back to in-memory checkpointing
   - Log warnings, not errors

2. **Checkpointer Setup Failure**
   - Startup fails gracefully
   - Prevents app from running without persistence
   - Clear error message

3. **Save/Restore Failure**
   - Log error, don't crash agent
   - Return empty history if retrieval fails
   - Notify user if critical

4. **Large State Objects**
   - Use blob storage automatically
   - Handle serialization errors
   - Cleanup old blobs periodically

### Logging Strategy

```python
logger.info("Checkpointer initialized for conversation {id}")
logger.warning(f"Failed to save checkpoint: {error}")
logger.error(f"Critical persistence error: {error}")
logger.debug(f"Checkpoint ID: {checkpoint_id}, size: {size}")
```

---

## Part 6: Testing Strategy

### Unit Tests
- Test checkpointer initialization
- Test save/retrieve operations
- Test error handling
- Test cleanup on shutdown

### Integration Tests
- Real PostgreSQL database
- Full conversation lifecycle
- Multiple concurrent conversations
- Large message histories

### Performance Tests
- Save 1000 messages, measure time
- Retrieve history with pagination
- Large state objects (100MB+)
- Connection pooling efficiency

---

## Part 7: Configuration & Deployment

### Environment Variables

```bash
# .env
PERSISTENCE_ENABLE_CHECKPOINTING=true
PERSISTENCE_MAX_CHECKPOINT_HISTORY=1000
PERSISTENCE_CHECKPOINTER_CLEANUP_TIMEOUT=5
```

### Docker Configuration

```dockerfile
# In Dockerfile
RUN apt-get install -y postgresql-client  # For psycopg
```

### Migration Commands

```bash
# Create migration
alembic revision --autogenerate -m "add checkpointer tables"

# Run migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

---

## Summary: Phase 1 Deliverables

✅ Architecture design document (this file)
✅ Module structure planned
✅ Database schema defined
✅ Integration points identified
✅ Error handling strategy
✅ Testing approach
✅ Configuration plan

**Next:** Phase 2 - Implementation

---

## Decisions Made

| Decision | Rationale | Alternative Considered |
|----------|-----------|------------------------|
| Use LangGraph AsyncPostgresSaver | Proven, maintained, tested | Custom implementation |
| Lazy initialization pattern | Efficient, safe startup | Eager initialization |
| Global instance management | Simple, accessible | Dependency injection |
| Custom storage adapter | Bridge to your code | Direct agent access |
| Auto-migration tables | Let LangGraph handle | Manual schema creation |
| Environment configuration | Flexibility, no code changes | Hardcoded config |

---

**Status:** ✅ PHASE 1 COMPLETE - Ready for Phase 2 Implementation
