from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TariffFOT(Base):
    """Справочник почасовых ставок ФОТ по ролям."""

    __tablename__ = "tariffs_fot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    hourly_rate_rub: Mapped[float] = mapped_column(Float, nullable=False)

    norms: Mapped[list["ProcessNorm"]] = relationship(back_populates="role", lazy="selectin")

    def __repr__(self) -> str:
        return f"<TariffFOT {self.role_name} @ {self.hourly_rate_rub} RUB/h>"


class ProcessNorm(Base):
    """Норматив длительности для конкретной операции."""

    __tablename__ = "process_norms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_name: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    norm_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("tariffs_fot.id"), nullable=False)

    role: Mapped["TariffFOT"] = relationship(back_populates="norms", lazy="joined")

    def __repr__(self) -> str:
        return f"<ProcessNorm {self.operation_name} norm={self.norm_seconds}s>"
