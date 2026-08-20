from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from database.models import Payment, User


class PaymentRepository:
    """Репозиторий для работы с платежами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        user_id: int,
        amount: int,
        package_id: str = None,
        provider: str = "telegram_stars",
        transaction_id: str = None
    ) -> Payment:
        """Создать запись о платеже"""
        payment = Payment(
            user_id=user_id,
            amount=amount,
            currency="💎",
            provider=provider,
            package_id=package_id,
            transaction_id=transaction_id,
            status="pending",
            created_at=datetime.utcnow()
        )
        self.session.add(payment)
        await self.session.flush()
        return payment
    
    async def get_by_id(self, payment_id: int) -> Optional[Payment]:
        """Получить платеж по ID"""
        return await self.session.get(Payment, payment_id)
    
    async def get_by_transaction_id(self, transaction_id: str) -> Optional[Payment]:
        """Получить платеж по ID транзакции"""
        result = await self.session.execute(
            select(Payment).where(Payment.transaction_id == transaction_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_user_id(self, user_id: int, limit: int = 20) -> List[Payment]:
        """Получить платежи пользователя"""
        result = await self.session.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(desc(Payment.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def mark_success(self, payment_id: int) -> Optional[Payment]:
        """Отметить платеж как успешный"""
        payment = await self.get_by_id(payment_id)
        if payment:
            payment.status = "success"
            payment.completed_at = datetime.utcnow()
            await self.session.flush()
        return payment
    
    async def mark_failed(self, payment_id: int, reason: str = None) -> Optional[Payment]:
        """Отметить платеж как неудачный"""
        payment = await self.get_by_id(payment_id)
        if payment:
            payment.status = "failed"
            payment.completed_at = datetime.utcnow()
            await self.session.flush()
        return payment
    
    async def get_successful_payments(self, user_id: int) -> List[Payment]:
        """Получить успешные платежи пользователя"""
        result = await self.session.execute(
            select(Payment)
            .where(
                and_(
                    Payment.user_id == user_id,
                    Payment.status == "success"
                )
            )
            .order_by(desc(Payment.created_at))
        )
        return result.scalars().all()
    
    async def get_total_spent(self, user_id: int) -> int:
        """Получить общую сумму потраченных лапок"""
        result = await self.session.execute(
            select(Payment)
            .where(
                and_(
                    Payment.user_id == user_id,
                    Payment.status == "success"
                )
            )
        )
        payments = result.scalars().all()
        return sum(p.amount for p in payments)