from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, 
    DateTime, ForeignKey, Text, UniqueConstraint, BigInteger
)
from sqlalchemy.orm import relationship
from database.connection import Base


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    coins = Column(Integer, default=500, nullable=False)
    premium_currency = Column(Integer, default=0, nullable=False)
    premium_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    main_message_id = Column(Integer, nullable=True)
    onboarding_step = Column(Integer, default=0, nullable=False)
    
    # ===== БАН =====
    is_banned = Column(Boolean, default=False, nullable=False)
    ban_reason = Column(String(255), nullable=True)
    banned_at = Column(DateTime, nullable=True)
    referred_by = Column(BigInteger, nullable=True)
    
    # Связи
    pets = relationship("Pet", back_populates="user", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")
    inventory = relationship("Inventory", back_populates="user", cascade="all, delete-orphan")
    daily_rewards = relationship("DailyReward", back_populates="user", uselist=False, cascade="all, delete-orphan")
    quest_progress = relationship("QuestProgress", back_populates="user", cascade="all, delete-orphan")
    gifts_sent = relationship("Gift", foreign_keys="Gift.from_user_id", back_populates="sender", cascade="all, delete-orphan")
    gifts_received = relationship("Gift", foreign_keys="Gift.to_user_id", back_populates="receiver", cascade="all, delete-orphan")
    gift_logs = relationship("GiftLog", foreign_keys="GiftLog.user_id", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    battlepass = relationship("BattlePass", back_populates="user", uselist=False, cascade="all, delete-orphan")
    post_likes = relationship("PostLike", back_populates="user", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    competition_participants = relationship("CompetitionParticipant", back_populates="user", cascade="all, delete-orphan")
    competition_results = relationship("CompetitionResult", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id}>"
    
    def is_premium(self) -> bool:
        if not self.premium_until:
            return False
        return datetime.utcnow() < self.premium_until


class Pet(Base):
    """Модель питомца"""
    __tablename__ = "pets"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    photo_file_id = Column(String(255), nullable=False)
    character_id = Column(String(50), nullable=False)
    game_id = Column(String(20), unique=True, nullable=False, index=True)
    
    level = Column(Integer, default=1, nullable=False)
    experience = Column(Integer, default=0, nullable=False)
    hunger = Column(Integer, default=0, nullable=False)
    stomach_capacity = Column(Integer, default=100, nullable=False)
    energy = Column(Integer, default=100, nullable=False)
    happiness = Column(Integer, default=50, nullable=False)
    luck = Column(Float, default=0.05, nullable=False)
    smell = Column(Integer, default=10, nullable=False)
    eating_speed = Column(Integer, default=10, nullable=False)
    
    title_id = Column(String(50), nullable=True)
    frame_id = Column(String(50), nullable=True)
    cosmetic_id = Column(String(50), nullable=True)
    
    total_eaten = Column(Integer, default=0)
    total_adventures = Column(Integer, default=0)
    total_overeat = Column(Integer, default=0)
    total_competitions = Column(Integer, default=0)
    competition_wins = Column(Integer, default=0)
    collected_items = Column(Integer, default=0)
    found_legendary = Column(Integer, default=0)
    last_active_date = Column(DateTime, default=datetime.utcnow)
    total_likes = Column(Integer, default=0)
    story_progress = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_adventure = Column(DateTime, nullable=True)
    last_recovery = Column(DateTime, default=datetime.utcnow)
    last_eat = Column(DateTime, nullable=True)
    last_hunger_update = Column(DateTime, default=datetime.utcnow)
    last_house_bonus = Column(DateTime, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="pets")
    house = relationship("House", back_populates="pet", uselist=False, cascade="all, delete-orphan")
    photos = relationship("Photo", back_populates="pet", cascade="all, delete-orphan")
    achievements = relationship("Achievement", back_populates="pet", cascade="all, delete-orphan")
    adventure_history = relationship("AdventureHistory", back_populates="pet", cascade="all, delete-orphan")
    food_stats = relationship("FoodStats", back_populates="pet", cascade="all, delete-orphan")
    cosmetics = relationship("PetCosmetic", back_populates="pet", cascade="all, delete-orphan")
    frames = relationship("PetFrame", back_populates="pet", cascade="all, delete-orphan")
    competition_participations = relationship("CompetitionParticipant", back_populates="pet", cascade="all, delete-orphan")
    competition_results = relationship("CompetitionResult", back_populates="pet", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="pet", cascade="all, delete-orphan")
    subscriptions_as_subscriber = relationship("Subscription", foreign_keys="Subscription.subscriber_pet_id", back_populates="subscriber", cascade="all, delete-orphan")
    subscriptions_as_target = relationship("Subscription", foreign_keys="Subscription.target_pet_id", back_populates="target", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="pet", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Pet id={self.id} name={self.name} game_id={self.game_id}>"
    
    def get_hunger_percent(self) -> float:
        return (self.hunger / self.stomach_capacity) * 100
    
    def get_max_hunger(self) -> int:
        return self.stomach_capacity * 2
    
    def get_hunger_status(self) -> tuple:
        percent = self.get_hunger_percent()
        if percent <= 0:
            return "💀", "Голодный"
        elif percent < 30:
            return "😫", "Очень голодный"
        elif percent < 60:
            return "😐", "Нормально"
        elif percent < 100:
            return "😊", "Сыт"
        elif percent <= 120:
            return "😋", "Обожрался"
        elif percent <= 150:
            return "🤢", "Тяжелый желудок"
        else:
            return "💀", "Катастрофический жор"
    
    def can_adventure(self) -> tuple:
        status, _ = self.get_hunger_status()
        if status == "💀":
            return False, "Слишком много съел! Нужно подождать."
        if self.energy < 10:
            return False, "Не хватает энергии! Отдохни."
        return True, ""


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_user_item"),)
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    item_id = Column(String(50), nullable=False)
    quantity = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="inventory")


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("pet_id", "achievement_id", name="uq_pet_achievement"),)
    
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    achievement_id = Column(String(50), nullable=False)
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    
    pet = relationship("Pet", back_populates="achievements")


class Photo(Base):
    """Модель фото питомца"""
    __tablename__ = "photos"
    
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    telegram_file_id = Column(String(255), nullable=False)
    caption = Column(Text, nullable=True)
    is_main = Column(Boolean, default=False)
    likes_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # ===== ПОЛЯ ДЛЯ МОДЕРАЦИИ =====
    is_approved = Column(Boolean, default=False, nullable=False)
    is_rejected = Column(Boolean, default=False, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, nullable=True)  # telegram_id админа
    reject_reason = Column(String(255), nullable=True)
    
    pet = relationship("Pet", back_populates="photos")
    posts = relationship("Post", back_populates="photo", cascade="all, delete-orphan")

class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("from_user_id", "pet_id", name="uq_like_user_pet"),)
    
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="likes")


class Gift(Base):
    __tablename__ = "gifts"
    
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    item_id = Column(String(50), nullable=False)
    item_type = Column(String(20), default="food", nullable=False)
    quantity = Column(Integer, default=1)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    is_claimed = Column(Boolean, default=False)
    claimed_at = Column(DateTime, nullable=True)
    
    sender = relationship("User", foreign_keys=[from_user_id], back_populates="gifts_sent")
    receiver = relationship("User", foreign_keys=[to_user_id], back_populates="gifts_received")


class GiftLog(Base):
    __tablename__ = "gift_logs"
    __table_args__ = (UniqueConstraint("user_id", "date", "item_rarity", name="uq_user_date_rarity"),)
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    item_id = Column(String(50), nullable=False)
    item_rarity = Column(String(20), nullable=False)
    quantity = Column(Integer, default=0)
    date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", foreign_keys=[user_id], back_populates="gift_logs")


class FoodStats(Base):
    __tablename__ = "food_stats"
    __table_args__ = (UniqueConstraint("pet_id", "food_id", name="uq_pet_food"),)
    
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    food_id = Column(String(50), nullable=False)
    count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    pet = relationship("Pet", back_populates="food_stats")


class AdventureHistory(Base):
    __tablename__ = "adventure_history"
    
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    location_id = Column(String(50), nullable=False)
    duration = Column(Integer, nullable=False)
    reward_type = Column(String(20), nullable=True)
    reward_amount = Column(Integer, nullable=True)
    reward_item_id = Column(String(50), nullable=True)
    event_id = Column(String(50), nullable=True)
    event_text = Column(Text, nullable=True)
    xp_gained = Column(Integer, default=0)
    coins_gained = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    pet = relationship("Pet", back_populates="adventure_history")


class AdventureCooldown(Base):
    __tablename__ = "adventure_cooldowns"
    __table_args__ = (UniqueConstraint("pet_id", "location_id", name="uq_pet_location_cooldown"),)
    
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    location_id = Column(String(50), nullable=False)
    cooldown_until = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailyReward(Base):
    __tablename__ = "daily_rewards"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    streak_days = Column(Integer, default=0)
    last_claim_date = Column(DateTime, nullable=True)
    next_claim_available = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="daily_rewards")


class QuestProgress(Base):
    __tablename__ = "quest_progress"
    __table_args__ = (UniqueConstraint("user_id", "quest_id", name="uq_user_quest"),)
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quest_id = Column(String(50), nullable=False)
    progress = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    claimed = Column(Boolean, default=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    claimed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="quest_progress")


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String(10), nullable=False, default="💎")
    provider = Column(String(50), nullable=True)
    status = Column(String(20), default="pending")
    package_id = Column(String(50), nullable=True)
    transaction_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="payments")


class PetCosmetic(Base):
    __tablename__ = "pet_cosmetics"
    __table_args__ = (UniqueConstraint("pet_id", "cosmetic_id", name="uq_pet_cosmetic"),)
    
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    cosmetic_id = Column(String(50), nullable=False)
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    
    pet = relationship("Pet", back_populates="cosmetics")


class PetFrame(Base):
    __tablename__ = "pet_frames"
    __table_args__ = (UniqueConstraint("pet_id", "frame_id", name="uq_pet_frame"),)
    
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    frame_id = Column(String(50), nullable=False)
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    
    pet = relationship("Pet", back_populates="frames")


class BattlePass(Base):
    __tablename__ = "battlepass"
    __table_args__ = (UniqueConstraint("user_id", "season_id", name="uq_user_season"),)
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    season_id = Column(Integer, default=1, nullable=False)
    level = Column(Integer, default=0)
    xp = Column(Integer, default=0)
    premium_unlocked = Column(Boolean, default=False)
    claimed_rewards = Column(Text, nullable=True, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="battlepass")


class Season(Base):
    __tablename__ = "seasons"
    
    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    competitions = relationship("Competition", back_populates="season", cascade="all, delete-orphan")


class Competition(Base):
    __tablename__ = "competitions"
    
    id = Column(Integer, primary_key=True)
    type = Column(String(50), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    participants_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    season = relationship("Season", back_populates="competitions")
    results = relationship("CompetitionResult", back_populates="competition", cascade="all, delete-orphan")


class CompetitionResult(Base):
    __tablename__ = "competition_results"
    
    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    score = Column(Integer, default=0)
    rank = Column(Integer, nullable=True)
    league_id = Column(String(50), nullable=True)
    rewards_claimed = Column(Boolean, default=False)
    reward_coins = Column(Integer, default=0)
    reward_xp = Column(Integer, default=0)
    reward_title = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    competition = relationship("Competition", back_populates="results")
    pet = relationship("Pet", back_populates="competition_results")
    user = relationship("User", back_populates="competition_results")


class CompetitionSeason(Base):
    __tablename__ = "competition_seasons"
    
    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    emoji = Column(String(10), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    participants = relationship("CompetitionParticipant", back_populates="season", cascade="all, delete-orphan")


class CompetitionParticipant(Base):
    __tablename__ = "competition_participants"
    __table_args__ = (UniqueConstraint("season_id", "pet_id", name="uq_season_pet"),)
    
    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey("competition_seasons.id"), nullable=False, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    points = Column(Integer, default=0)
    total_eaten = Column(Integer, default=0)
    total_adventures = Column(Integer, default=0)
    total_likes_received = Column(Integer, default=0)
    unique_foods_eaten = Column(Integer, default=0)
    legendary_found = Column(Integer, default=0)
    
    rank = Column(Integer, nullable=True)
    league_id = Column(String(50), nullable=True)
    rewards_claimed = Column(Boolean, default=False)
    reward_coins = Column(Integer, default=0)
    reward_premium_currency = Column(Integer, default=0)
    reward_title = Column(String(100), nullable=True)
    reward_cosmetic = Column(String(50), nullable=True)
    
    joined_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    season = relationship("CompetitionSeason", back_populates="participants")
    pet = relationship("Pet", back_populates="competition_participations")
    user = relationship("User", back_populates="competition_participants")


class CompetitionLeaderboard(Base):
    __tablename__ = "competition_leaderboard"
    __table_args__ = (UniqueConstraint("season_id", "pet_id", name="uq_leaderboard_season_pet"),)
    
    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey("competition_seasons.id"), nullable=False, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    rank = Column(Integer, nullable=True)
    points = Column(Integer, default=0)
    league_id = Column(String(50), nullable=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    pet = relationship("Pet")
    user = relationship("User")


class House(Base):
    __tablename__ = "houses"
    
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, unique=True, index=True)
    template_id = Column(String(50), default="basic", nullable=False)
    level = Column(Integer, default=1, nullable=False)
    
    energy_recovery_boost = Column(Integer, default=0)
    happiness_boost = Column(Integer, default=0)
    hunger_reduction = Column(Integer, default=0)
    luck_boost = Column(Integer, default=0)
    
    total_visits = Column(Integer, default=0)
    total_visitors = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    pet = relationship("Pet", back_populates="house")
    rooms = relationship("HouseRoom", back_populates="house", cascade="all, delete-orphan")
    decorations = relationship("HouseDecoration", back_populates="house", cascade="all, delete-orphan")
    visitors = relationship("HouseVisit", back_populates="house", cascade="all, delete-orphan")


class HouseRoom(Base):
    __tablename__ = "house_rooms"
    __table_args__ = (UniqueConstraint("house_id", "room_type", name="uq_house_room_type"),)
    
    id = Column(Integer, primary_key=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=False, index=True)
    room_type = Column(String(50), nullable=False)
    is_unlocked = Column(Boolean, default=False)
    bonuses = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    house = relationship("House", back_populates="rooms")
    furniture = relationship("HouseFurniture", back_populates="room", cascade="all, delete-orphan")


class HouseFurniture(Base):
    __tablename__ = "house_furniture"
    __table_args__ = (UniqueConstraint("room_id", "furniture_id", name="uq_room_furniture"),)
    
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("house_rooms.id"), nullable=False, index=True)
    furniture_id = Column(String(50), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    bonuses = Column(Text, nullable=True)
    
    placed_at = Column(DateTime, default=datetime.utcnow)
    
    room = relationship("HouseRoom", back_populates="furniture")


class HouseDecoration(Base):
    __tablename__ = "house_decorations"
    
    id = Column(Integer, primary_key=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=False, index=True)
    decoration_id = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    placed_at = Column(DateTime, default=datetime.utcnow)
    
    house = relationship("House", back_populates="decorations")


class HouseVisit(Base):
    __tablename__ = "house_visits"
    __table_args__ = (UniqueConstraint("house_id", "visitor_pet_id", "visit_date", name="uq_house_visitor_day"),)
    
    id = Column(Integer, primary_key=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=False, index=True)
    visitor_pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    visit_date = Column(DateTime, default=datetime.utcnow)
    reward_coins = Column(Integer, default=0)
    reward_happiness = Column(Integer, default=0)
    
    house = relationship("House", back_populates="visitors")
    visitor_pet = relationship("Pet")


class HouseUpgradeLog(Base):
    __tablename__ = "house_upgrade_logs"
    
    id = Column(Integer, primary_key=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=False, index=True)
    upgrade_type = Column(String(50), nullable=False)
    old_value = Column(String(100), nullable=True)
    new_value = Column(String(100), nullable=True)
    cost_coins = Column(Integer, default=0)
    cost_premium = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    house = relationship("House")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    pet = relationship("Pet", back_populates="chat_messages")


class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False, index=True)
    caption = Column(Text, nullable=True)
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    is_published = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    pet = relationship("Pet", back_populates="posts")
    photo = relationship("Photo", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("PostLike", back_populates="post", cascade="all, delete-orphan")


class PostLike(Base):
    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_post_like"),)
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="post_likes")
    post = relationship("Post", back_populates="likes")


class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    
    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")
    pet = relationship("Pet")
    parent = relationship("Comment", remote_side=[id], backref="replies")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("subscriber_pet_id", "target_pet_id", name="uq_subscription"),)
    
    id = Column(Integer, primary_key=True)
    subscriber_pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    target_pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    subscriber = relationship("Pet", foreign_keys=[subscriber_pet_id], back_populates="subscriptions_as_subscriber")
    target = relationship("Pet", foreign_keys=[target_pet_id], back_populates="subscriptions_as_target")


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    text = Column(Text, nullable=False)
    data = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="notifications")