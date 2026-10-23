import pytest

from askless.engine import compile_questions, execute, explore, parse_csv
from askless.models import DecisionKey, Policy, Question

CSV = "email,name\nada@example.com,Old\nada@example.com,New\nbad,Invalid\nlin@example.com,Lin\n"


def questions(scope: str) -> list[Question]:
    return [
        Question(id=f"{agent}-{key}", agent_id=agent, decision_key=key, scope=scope, prompt=f"{agent}: {key}?")
        for agent in ["data", "quality", "delivery"]
        for key in DecisionKey
    ]


def test_real_branches_keep_different_records_and_quarantine_invalid_rows() -> None:
    dataset = parse_csv(CSV)
    first = execute(dataset, Policy(duplicates="first", invalid="quarantine", email_case="preserve"))
    last = execute(dataset, Policy(duplicates="last", invalid="quarantine", email_case="preserve"))
    assert [row["name"] for row in first.rows] == ["Old", "Lin"]
    assert [row["name"] for row in last.rows] == ["New", "Lin"]
    assert first.quarantined[0].line == 4
    assert first.output_hash != last.output_hash
    assert first.duplicate_count == 1


def test_blocked_execution_exports_no_successful_rows() -> None:
    result = execute(parse_csv(CSV), Policy(invalid="block"))
    assert result.blocked
    assert result.rows == []
    assert len(result.quarantined) == 1


def test_compile_merges_by_contract_and_eliminates_only_observed_equivalence() -> None:
    dataset = parse_csv(CSV)
    trials = explore(dataset)
    groups = compile_questions(questions(dataset.scope), trials, dataset.scope)
    assert len(trials) == 8
    assert len(groups) == 3
    assert [g.key for g in groups if g.status == "auto"] == [DecisionKey.email_case]
    assert all(len(g.question_ids) == 3 for g in groups)
    assert len([g for g in groups if g.status == "pending"]) == 2


def test_compiler_checks_all_other_policy_combinations() -> None:
    dataset = parse_csv(CSV)
    groups = compile_questions(questions(dataset.scope), explore(dataset), dataset.scope)
    # Duplicates are invisible in blocked branches, but matter in quarantine branches.
    duplicate = next(g for g in groups if g.key == DecisionKey.duplicates)
    assert duplicate.status == "pending"
    assert len(duplicate.witnesses) == 2


def test_case_change_is_not_auto_resolved_when_input_has_uppercase_email() -> None:
    dataset = parse_csv("email,name\nAda@Example.com,Ada\n")
    groups = compile_questions(questions(dataset.scope), explore(dataset), dataset.scope)
    assert next(g for g in groups if g.key == DecisionKey.email_case).status == "pending"


def test_cross_scope_question_and_incomplete_evidence_are_rejected() -> None:
    dataset = parse_csv(CSV)
    with pytest.raises(ValueError, match="scope"):
        compile_questions(questions("different-dataset"), explore(dataset), dataset.scope)
    with pytest.raises(ValueError, match="complete"):
        compile_questions(questions(dataset.scope), explore(dataset)[:2], dataset.scope)


@pytest.mark.parametrize("text", ["", "name\nAda\n", "email,email\na,b\n", "email,name\na,b,extra\n", 'email,name\n"unfinished'])
def test_malformed_csv_fails_before_any_trial(text: str) -> None:
    with pytest.raises(ValueError):
        parse_csv(text)


def test_scope_binds_complete_input_and_csv_formula_export_is_safe() -> None:
    from askless.engine import export_csv

    left = parse_csv("email,name\na@example.com,=1+1\n")
    right = parse_csv("email,name\na@example.com,Ada\n")
    assert left.scope != right.scope
    assert "'=1+1" in export_csv(execute(left, Policy()).rows, left.columns)


@pytest.mark.parametrize("email", ["bob@exa/mple.com", "bob@exa_mple.com", "bob@-example.com", "bob@example..com"])
def test_invalid_domain_never_bypasses_block_policy(email: str) -> None:
    result = execute(parse_csv(f"email,name\n{email},Bob\n"), Policy(invalid="block"))
    assert result.blocked
    assert result.rows == []
    assert len(result.quarantined) == 1


@pytest.mark.parametrize("column", ["x" * 129, "列" * 43])
def test_column_byte_limit_prevents_repeated_key_storage_amplification(column: str) -> None:
    with pytest.raises(ValueError, match="列名"):
        parse_csv(f"email,{column}\na@example.com,value\n")


def test_expanded_dataset_budget_is_checked_before_trials() -> None:
    columns = ["email"] + [f"column{i}" + "x" * 80 for i in range(29)]
    rows = [f"user{i}@example.com" + ",x" * 29 for i in range(400)]
    text = "\n".join([",".join(columns), *rows])
    assert len(text.encode()) < 262_144
    with pytest.raises(ValueError, match="512 KiB"):
        parse_csv(text)
