"""Tax calculator tests — 100% coverage required.

All values in cents. Standard deductions per P.L. 119-21:
  single: $15,750 (1,575,000 cents)
  married_joint: $31,500 (3,150,000 cents)
  married_separate: $15,750 (1,575,000 cents)
  head_of_household: $23,625 (2,362,500 cents)
"""

import pytest

from app.services.tax_calculator import (
    calculate_federal_tax,
    calculate_return,
    get_standard_deduction,
)


class TestStandardDeductions:
    def test_single(self):
        assert get_standard_deduction("single") == 1_575_000

    def test_married_joint(self):
        assert get_standard_deduction("married_joint") == 3_150_000

    def test_married_separate(self):
        assert get_standard_deduction("married_separate") == 1_575_000

    def test_head_of_household(self):
        assert get_standard_deduction("head_of_household") == 2_362_500

    def test_invalid_status(self):
        with pytest.raises(ValueError, match="Unknown filing status"):
            get_standard_deduction("invalid")


class TestFederalTax:
    def test_zero_income(self):
        assert calculate_federal_tax(0, "single") == 0

    def test_negative_income(self):
        assert calculate_federal_tax(-100_00, "single") == 0

    def test_single_10_percent_only(self):
        # $10,000 taxable = 1,000,000 cents, all in 10% bracket
        assert calculate_federal_tax(1_000_000, "single") == 100_000

    def test_single_first_bracket_boundary(self):
        # $11,925 = 1,192,500 cents — top of 10% bracket
        assert calculate_federal_tax(1_192_500, "single") == 119_250

    def test_single_into_12_percent(self):
        # $20,000 taxable = 2,000,000 cents
        # 10% on first 1,192,500 = 119,250
        # 12% on next 807,500 = 96,900
        # total = 216,150
        assert calculate_federal_tax(2_000_000, "single") == 216_150

    def test_single_second_bracket_boundary(self):
        # $48,475 = 4,847,500 cents — top of 12% bracket
        # 10% on 1,192,500 = 119,250
        # 12% on 3,655,000 = 438,600
        # total = 557,850
        assert calculate_federal_tax(4_847_500, "single") == 557_850

    def test_single_into_22_percent(self):
        # $60,000 = 6,000,000 cents
        # 10% on 1,192,500 = 119,250
        # 12% on 3,655,000 = 438,600
        # 22% on 1,152,500 = 253,550
        # total = 811,400
        assert calculate_federal_tax(6_000_000, "single") == 811_400

    def test_single_into_24_percent(self):
        # $110,000 = 11,000,000 cents
        # 10% on 1,192,500 = 119,250
        # 12% on 3,655,000 = 438,600
        # 22% on 5,487,500 = 1,207,250
        # 24% on 665,000 = 159,600
        # total = 1,924,700
        assert calculate_federal_tax(11_000_000, "single") == 1_924_700

    def test_married_joint_10_percent(self):
        # $20,000 = 2,000,000 cents, all in 10% bracket (max is 2,385,000)
        assert calculate_federal_tax(2_000_000, "married_joint") == 200_000

    def test_married_joint_first_boundary(self):
        # $23,850 = 2,385,000 cents
        assert calculate_federal_tax(2_385_000, "married_joint") == 238_500

    def test_married_joint_into_12(self):
        # $50,000 = 5,000,000 cents
        # 10% on 2,385,000 = 238,500
        # 12% on 2,615,000 = 313,800
        # total = 552,300
        assert calculate_federal_tax(5_000_000, "married_joint") == 552_300

    def test_head_of_household_10_percent(self):
        # $15,000 = 1,500,000 cents
        assert calculate_federal_tax(1_500_000, "head_of_household") == 150_000

    def test_head_of_household_boundary(self):
        # $17,000 = 1,700,000 cents
        assert calculate_federal_tax(1_700_000, "head_of_household") == 170_000

    def test_head_of_household_into_12(self):
        # $30,000 = 3,000,000 cents
        # 10% on 1,700,000 = 170,000
        # 12% on 1,300,000 = 156,000
        # total = 326,000
        assert calculate_federal_tax(3_000_000, "head_of_household") == 326_000

    def test_married_separate_same_as_single(self):
        income = 5_000_000
        assert calculate_federal_tax(income, "married_separate") == calculate_federal_tax(
            income, "single"
        )

    def test_invalid_status(self):
        with pytest.raises(ValueError, match="Unknown filing status"):
            calculate_federal_tax(1_000_000, "invalid")


class TestCalculateReturn:
    def test_refund_scenario(self):
        # $50,000 wages, $8,000 federal withheld, $2,000 state withheld, single
        result = calculate_return(
            total_wages_cents=5_000_000,
            total_federal_withheld_cents=800_000,
            total_state_withheld_cents=200_000,
            filing_status="single",
        )
        assert result["adjusted_gross_income"] == 5_000_000
        assert result["standard_deduction"] == 1_575_000
        assert result["taxable_income"] == 3_425_000
        # 10% on 1,192,500 = 119,250
        # 12% on 2,232,500 = 267,900
        # total federal_tax = 387,150
        assert result["federal_tax"] == 387_150
        assert result["total_withheld"] == 1_000_000
        # net = total_withheld - total_tax = 1,000,000 - 387,150 = 612,850
        assert result["refund_amount"] == 612_850
        assert result["owed_amount"] == 0

    def test_owed_scenario(self):
        # $80,000 wages, $3,000 federal withheld, single
        result = calculate_return(
            total_wages_cents=8_000_000,
            total_federal_withheld_cents=300_000,
            total_state_withheld_cents=0,
            filing_status="single",
        )
        assert result["adjusted_gross_income"] == 8_000_000
        assert result["taxable_income"] == 8_000_000 - 1_575_000  # 6,425,000
        # Federal tax on 6,425,000:
        # 10% on 1,192,500 = 119,250
        # 12% on 3,655,000 = 438,600
        # 22% on 1,577,500 = 347,050
        # total = 904,900
        assert result["federal_tax"] == 904_900
        assert result["refund_amount"] == 0
        assert result["owed_amount"] == 904_900 - 300_000  # 604,900

    def test_zero_income(self):
        result = calculate_return(
            total_wages_cents=0,
            total_federal_withheld_cents=0,
            total_state_withheld_cents=0,
            filing_status="single",
        )
        assert result["taxable_income"] == 0
        assert result["federal_tax"] == 0
        assert result["refund_amount"] == 0
        assert result["owed_amount"] == 0

    def test_deduction_exceeds_income(self):
        # $10,000 wages — below standard deduction
        result = calculate_return(
            total_wages_cents=1_000_000,
            total_federal_withheld_cents=50_000,
            total_state_withheld_cents=0,
            filing_status="single",
        )
        assert result["taxable_income"] == 0
        assert result["federal_tax"] == 0
        assert result["refund_amount"] == 50_000
        assert result["owed_amount"] == 0

    def test_married_joint_deduction(self):
        result = calculate_return(
            total_wages_cents=7_000_000,
            total_federal_withheld_cents=500_000,
            total_state_withheld_cents=0,
            filing_status="married_joint",
        )
        assert result["standard_deduction"] == 3_150_000
        assert result["taxable_income"] == 3_850_000
        # 10% on 2,385,000 = 238,500
        # 12% on 1,465,000 = 175,800
        # total = 414,300
        assert result["federal_tax"] == 414_300

    def test_head_of_household_deduction(self):
        result = calculate_return(
            total_wages_cents=5_000_000,
            total_federal_withheld_cents=500_000,
            total_state_withheld_cents=0,
            filing_status="head_of_household",
        )
        assert result["standard_deduction"] == 2_362_500
        assert result["taxable_income"] == 2_637_500
        # 10% on 1,700,000 = 170,000
        # 12% on 937,500 = 112,500
        # total = 282,500
        assert result["federal_tax"] == 282_500

    def test_withheld_includes_state(self):
        result = calculate_return(
            total_wages_cents=5_000_000,
            total_federal_withheld_cents=400_000,
            total_state_withheld_cents=100_000,
            filing_status="single",
        )
        assert result["total_withheld"] == 500_000
