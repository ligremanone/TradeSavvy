import asyncio

from tinkoff.invest.grpc.instruments_pb2 import INSTRUMENT_ID_TYPE_FIGI

from app.client import TinkoffClient
from app.stats.sqlite_client import StatsSQLiteClient
from app.strategies.models import StrategyName
from tinkoff.invest import OrderExecutionReportStatus, AioRequestError

from app.utils.quotation import quotation_to_float

FINAL_ORDER_STATUS = [
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL,
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_CANCELLED,
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_REJECTED,
]
ORDER_DIRECTION = {
    0: "Значение не указано",
    1: "Покупка",
    2: "Продажа",
}
ORDER_EXECUTION_REPORT_STATUS = {
    0: "none",
    1: "Исполнена",
    2: "Отклонена",
    3: "Отменена пользователем",
    4: "Новая",
    5: "Частично исполнена",
}


class StatsHandler:
    def __init__(self, strategy: StrategyName, broker_client: TinkoffClient):
        self.strategy = strategy
        self.db = StatsSQLiteClient(db_name="stats.db")
        self.broker_client = broker_client

    async def handle_new_order(self, account_id: str, order_id: str):
        try:
            order_state = await self.broker_client.get_order_state(
                account_id=account_id, order_id=order_id
            )
        except AioRequestError:
            return
        self.db.add_order(
            order_id=order_id,
            ticker=(
                await self.broker_client.get_ticker(
                    id_type=INSTRUMENT_ID_TYPE_FIGI,
                    id=order_state.figi,
                )
            ),
            figi=order_state.figi,
            order_direction=ORDER_DIRECTION.get(order_state.direction),
            price=quotation_to_float(order_state.total_order_amount),
            quantity=order_state.lots_requested,
            status=ORDER_EXECUTION_REPORT_STATUS.get(
                order_state.execution_report_status
            ),
        )
        while order_state.execution_report_status not in FINAL_ORDER_STATUS:
            await asyncio.sleep(10)
            order_state = await self.broker_client.get_order_state(
                account_id=account_id, order_id=order_id
            )
        self.db.update_order_status(
            order_id=order_id,
            status=ORDER_EXECUTION_REPORT_STATUS.get(
                order_state.execution_report_status
            ),
        )
