import asyncio

from orchai.application.policies import AutomaticExecutionPolicy
from orchai.domain.actions import ActionName
from orchai.domain.roles import RoleName
from orchai.infrastructure.persistence import (
    SQLAlchemyAutomaticPolicyRepository,
    SQLAlchemyDatabase,
)


def test_get_returns_default_when_nothing_persisted_yet(tmp_path) -> None:
    async def run() -> None:
        database = SQLAlchemyDatabase(f"sqlite:///{tmp_path / 'orchai.db'}")
        database.migrate()
        repository = SQLAlchemyAutomaticPolicyRepository(database)

        policy = await repository.get()

        assert policy == AutomaticExecutionPolicy()

    asyncio.run(run())


def test_set_then_get_round_trips_the_policy(tmp_path) -> None:
    async def run() -> None:
        database = SQLAlchemyDatabase(f"sqlite:///{tmp_path / 'orchai.db'}")
        database.migrate()
        repository = SQLAlchemyAutomaticPolicyRepository(database)

        written = AutomaticExecutionPolicy(
            allowed_operations=(
                (RoleName.DEVELOPER, ActionName.IMPLEMENT),
                (RoleName.QUALITY_AGENT, ActionName.TEST),
            ),
            allowed_cross_role_transitions=(
                (RoleName.DEVELOPER, RoleName.QUALITY_AGENT),
            ),
            allow_model_substitution=True,
            allow_context_expansion=True,
        )
        await repository.set(written)

        read_back = await repository.get()

        assert read_back == written

    asyncio.run(run())


def test_set_replaces_the_previous_policy_not_appends(tmp_path) -> None:
    async def run() -> None:
        database = SQLAlchemyDatabase(f"sqlite:///{tmp_path / 'orchai.db'}")
        database.migrate()
        repository = SQLAlchemyAutomaticPolicyRepository(database)

        await repository.set(
            AutomaticExecutionPolicy(
                allowed_operations=((RoleName.DEVELOPER, ActionName.IMPLEMENT),)
            )
        )
        await repository.set(
            AutomaticExecutionPolicy(
                allowed_operations=((RoleName.QUALITY_AGENT, ActionName.TEST),)
            )
        )

        policy = await repository.get()

        assert policy.allowed_operations == ((RoleName.QUALITY_AGENT, ActionName.TEST),)

    asyncio.run(run())


def test_policy_survives_a_restart(tmp_path) -> None:
    async def run() -> None:
        database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
        database = SQLAlchemyDatabase(database_url)
        database.migrate()
        repository = SQLAlchemyAutomaticPolicyRepository(database)
        await repository.set(
            AutomaticExecutionPolicy(
                allowed_operations=((RoleName.DEVELOPER, ActionName.IMPLEMENT),),
                allow_model_substitution=True,
            )
        )

        restarted_database = SQLAlchemyDatabase(database_url)
        restarted_database.migrate()
        restarted_repository = SQLAlchemyAutomaticPolicyRepository(restarted_database)

        policy = await restarted_repository.get()

        assert policy.allowed_operations == ((RoleName.DEVELOPER, ActionName.IMPLEMENT),)
        assert policy.allow_model_substitution is True

    asyncio.run(run())
