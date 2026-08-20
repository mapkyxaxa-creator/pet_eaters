import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.repositories.payment_repository import PaymentRepository
from services.data_loader import data_loader

logger = logging.getLogger(__name__)


class PaymentService:
    """Сервис для работы с платежами и премиум-валютой"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.payment_repo = PaymentRepository(session)
        self.packages = data_loader.get("payments", {}).get("packages", [])
    
    async def get_packages(self) -> List[Dict[str, Any]]:
        """Получить список доступных пакетов лапок"""
        return self.packages
    
    async def get_package(self, package_id: str) -> Optional[Dict[str, Any]]:
        """Получить пакет по ID"""
        for package in self.packages:
            if package.get("id") == package_id:
                return package
        return None
    
    async def create_payment(
        self,
        user_id: int,
        package_id: str,
        transaction_id: str = None
    ) -> Dict[str, Any]:
        """
        Создать платёж
        
        Args:
            user_id: Telegram ID пользователя
            package_id: ID пакета
            transaction_id: ID транзакции от Telegram (опционально)
        
        Returns:
            {
                "success": bool,
                "message": str,
                "payment_id": int,
                "amount": int
            }
        """
        # Проверяем пакет
        package = await self.get_package(package_id)
        if not package:
            return {"success": False, "message": "Пакет не найден"}
        
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        amount = package.get("amount", 0)
        bonus = package.get("bonus", 0)
        total_amount = amount + bonus
        
        # Создаём запись о платеже
        payment = await self.payment_repo.create(
            user_id=user.id,
            amount=total_amount,
            package_id=package_id,
            provider="telegram_stars",
            transaction_id=transaction_id
        )
        
        await self.session.flush()
        
        logger.info(f"Создан платёж {payment.id} для пользователя {user_id} на {total_amount} 💎")
        
        return {
            "success": True,
            "message": f"Платёж создан! Пакет: {package.get('name')}",
            "payment_id": payment.id,
            "amount": total_amount,
            "package": package
        }
    
    async def complete_payment(self, payment_id: int) -> Dict[str, Any]:
        """
        Завершить платёж (начислить лапки)
        
        Args:
            payment_id: ID платежа
        
        Returns:
            {
                "success": bool,
                "message": str,
                "amount": int
            }
        """
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            return {"success": False, "message": "Платёж не найден"}
        
        if payment.status == "success":
            return {"success": False, "message": "Платёж уже завершён"}
        
        if payment.status == "failed":
            return {"success": False, "message": "Платёж был отменён"}
        
        # Начисляем лапки
        user = await self.user_repo.get_by_id(payment.user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        user.premium_currency += payment.amount
        
        # Отмечаем платеж как успешный
        await self.payment_repo.mark_success(payment_id)
        
        await self.session.flush()
        
        logger.info(f"Платёж {payment_id} завершён, начислено {payment.amount} 💎 пользователю {user.telegram_id}")
        
        return {
            "success": True,
            "message": f"✅ Начислено {payment.amount} 💎!",
            "amount": payment.amount,
            "balance": user.premium_currency
        }
    
    async def fail_payment(self, payment_id: int, reason: str = None) -> Dict[str, Any]:
        """Отменить платёж"""
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            return {"success": False, "message": "Платёж не найден"}
        
        if payment.status != "pending":
            return {"success": False, "message": f"Платёж уже {payment.status}"}
        
        await self.payment_repo.mark_failed(payment_id, reason)
        await self.session.flush()
        
        return {
            "success": True,
            "message": "Платёж отменён"
        }
    
    async def get_balance(self, user_id: int) -> Dict[str, Any]:
        """Получить баланс лапок"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        return {
            "success": True,
            "premium_currency": user.premium_currency
        }
    
    async def add_premium_currency(self, user_id: int, amount: int) -> Dict[str, Any]:
        """Добавить лапки (административное)"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        user.premium_currency += amount
        await self.session.flush()
        
        logger.info(f"Административное начисление {amount} 💎 пользователю {user_id}")
        
        return {
            "success": True,
            "message": f"Начислено {amount} 💎",
            "balance": user.premium_currency
        }
    
    async def get_payment_history(self, user_id: int, limit: int = 20) -> Dict[str, Any]:
        """Получить историю платежей"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        payments = await self.payment_repo.get_by_user_id(user.id, limit)
        
        return {
            "success": True,
            "payments": [
                {
                    "id": p.id,
                    "amount": p.amount,
                    "status": p.status,
                    "package_id": p.package_id,
                    "created_at": p.created_at.strftime("%d.%m.%Y %H:%M"),
                    "completed_at": p.completed_at.strftime("%d.%m.%Y %H:%M") if p.completed_at else None
                }
                for p in payments
            ]
        }