# -*- coding: utf-8 -*-
"""
Unit tests for v41_models.py

Tests Member dataclass validation, serialization, and normalization.
"""

import unittest
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from models import Member, validate_member_data, sanitize_member_input
from exceptions import (
    ValidationError,
    RequiredFieldError,
    InvalidFormatError
)


class TestMemberCreation(unittest.TestCase):
    """Test Member creation and basic functionality."""
    
    def test_create_valid_member(self):
        """Test creating a valid member."""
        member = Member(
            nome="Mario",
            cognome="Rossi",
            email="mario@example.com"
        )
        
        self.assertEqual(member.nome, "Mario")
        self.assertEqual(member.cognome, "Rossi")
        self.assertEqual(member.email, "mario@example.com")
    
    def test_member_str_representation(self):
        """Test string representation of member."""
        member = Member(
            nome="Mario",
            cognome="Rossi",
            matricola="001"
        )
        
        str_repr = str(member)
        self.assertIn("Rossi Mario", str_repr)
        self.assertIn("001", str_repr)


class TestRequiredFields(unittest.TestCase):
    """Test required field validation."""
    
    def test_missing_nome(self):
        """Test that missing nome raises RequiredFieldError."""
        with self.assertRaises(RequiredFieldError) as context:
            Member(nome="", cognome="Rossi")
        
        self.assertIn("nome", str(context.exception).lower())
    
    def test_missing_cognome(self):
        """Test that missing cognome raises RequiredFieldError."""
        with self.assertRaises(RequiredFieldError) as context:
            Member(nome="Mario", cognome="")
        
        self.assertIn("cognome", str(context.exception).lower())
    
    def test_none_nome(self):
        """Test that None nome raises RequiredFieldError."""
        with self.assertRaises(RequiredFieldError):
            Member(nome=None, cognome="Rossi")  # type: ignore
    
    def test_whitespace_only_nome(self):
        """Test that whitespace-only nome raises RequiredFieldError."""
        with self.assertRaises(RequiredFieldError):
            Member(nome="   ", cognome="Rossi")


class TestEmailValidation(unittest.TestCase):
    """Test email validation and normalization."""
    
    def test_valid_email(self):
        """Test valid email formats."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.com",
            "123@test.com"
        ]
        
        for email in valid_emails:
            member = Member(nome="Test", cognome="User", email=email)
            self.assertIsNotNone(member.email)
    
    def test_email_normalization(self):
        """Test that emails are normalized to lowercase."""
        member = Member(
            nome="Test",
            cognome="User",
            email="Test.User@EXAMPLE.COM"
        )
        
        self.assertEqual(member.email, "test.user@example.com")
    
    def test_invalid_email_format(self):
        """Test invalid email formats."""
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user @example.com",
            "user@.com"
        ]
        
        for email in invalid_emails:
            with self.assertRaises(InvalidFormatError):
                Member(nome="Test", cognome="User", email=email)
    
    def test_empty_email_allowed(self):
        """Test that empty email is allowed (optional field)."""
        member = Member(nome="Test", cognome="User", email="")
        self.assertEqual(member.email, "")
        
        member = Member(nome="Test", cognome="User", email=None)
        self.assertIsNone(member.email)


class TestCodiceFiscaleValidation(unittest.TestCase):
    """Test codice fiscale validation and normalization."""
    
    def test_valid_codicefiscale(self):
        """Test valid codice fiscale format."""
        member = Member(
            nome="Test",
            cognome="User",
            codicefiscale="RSSMRA80A01H501U"
        )
        
        self.assertEqual(member.codicefiscale, "RSSMRA80A01H501U")
    
    def test_codicefiscale_normalization(self):
        """Test that codice fiscale is normalized to uppercase."""
        member = Member(
            nome="Test",
            cognome="User",
            codicefiscale="rssmra80a01h501u"
        )
        
        self.assertEqual(member.codicefiscale, "RSSMRA80A01H501U")
    
    def test_invalid_codicefiscale_length(self):
        """Test invalid codice fiscale length."""
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", codicefiscale="TOOSHORT")
    
    def test_invalid_codicefiscale_chars(self):
        """Test invalid characters in codice fiscale."""
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", codicefiscale="RSSMRA80A01H501!")
    
    def test_empty_codicefiscale_allowed(self):
        """Test that empty codice fiscale is allowed."""
        member = Member(nome="Test", cognome="User", codicefiscale="")
        self.assertEqual(member.codicefiscale, "")


class TestCAPValidation(unittest.TestCase):
    """Test CAP (postal code) validation."""
    
    def test_valid_cap(self):
        """Test valid CAP format."""
        member = Member(nome="Test", cognome="User", cap="12345")
        self.assertEqual(member.cap, "12345")
    
    def test_invalid_cap_length(self):
        """Test invalid CAP length."""
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", cap="1234")
        
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", cap="123456")
    
    def test_invalid_cap_chars(self):
        """Test non-numeric CAP."""
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", cap="1234A")
    
    def test_empty_cap_allowed(self):
        """Test that empty CAP is allowed."""
        member = Member(nome="Test", cognome="User", cap="")
        self.assertEqual(member.cap, "")


class TestProvinciaValidation(unittest.TestCase):
    """Test provincia (province) validation."""
    
    def test_valid_provincia(self):
        """Test valid provincia format."""
        member = Member(nome="Test", cognome="User", provincia="BG")
        self.assertEqual(member.provincia, "BG")
    
    def test_provincia_normalization(self):
        """Test that provincia is normalized to uppercase."""
        member = Member(nome="Test", cognome="User", provincia="bg")
        self.assertEqual(member.provincia, "BG")
    
    def test_invalid_provincia_length(self):
        """Test invalid provincia length."""
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", provincia="B")
        
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", provincia="BGG")
    
    def test_invalid_provincia_chars(self):
        """Test non-alphabetic provincia."""
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", provincia="B1")
    
    def test_empty_provincia_allowed(self):
        """Test that empty provincia is allowed."""
        member = Member(nome="Test", cognome="User", provincia="")
        self.assertEqual(member.provincia, "")


class TestDateValidation(unittest.TestCase):
    """Test date field validation."""
    
    def test_valid_date(self):
        """Test valid date format."""
        member = Member(
            nome="Test",
            cognome="User",
            data_nascita="1990-01-15"
        )
        
        self.assertEqual(member.data_nascita, "1990-01-15")
    
    def test_invalid_date_format(self):
        """Test invalid date formats."""
        invalid_dates = [
            "15/01/1990",  # Wrong format
            "1990-1-15",   # Missing zero padding
            "1990-13-01",  # Invalid month
            "1990-02-30",  # Invalid day
            "not-a-date"
        ]
        
        for date in invalid_dates:
            with self.assertRaises(InvalidFormatError):
                Member(nome="Test", cognome="User", data_nascita=date)
    
    def test_empty_date_allowed(self):
        """Test that empty dates are allowed."""
        member = Member(nome="Test", cognome="User", data_nascita="")
        self.assertEqual(member.data_nascita, "")
        
        member = Member(nome="Test", cognome="User", data_nascita=None)
        self.assertIsNone(member.data_nascita)
    
    def test_all_date_fields(self):
        """Test that all date fields are validated."""
        date_fields = [
            'data_nascita',
            'data_iscrizione',
            'data_dimissioni',
            'delibera_data',
        ]
        
        for field in date_fields:
            # Valid date should work
            member = Member(
                nome="Test",
                cognome="User",
                **{field: "2024-01-15"}  # type: ignore[arg-type]
            )
            self.assertEqual(getattr(member, field), "2024-01-15")
            
            # Invalid date should raise error
            with self.assertRaises(InvalidFormatError):
                Member(
                    nome="Test",
                    cognome="User",
                    **{field: "invalid-date"}  # type: ignore[arg-type]
                )


class TestQuotaValidation(unittest.TestCase):
    """Test quota code validation."""
    
    def test_valid_quota_codes(self):
        """Test valid quota code formats."""
        valid_codes = ["4", "A", "AA", "AB", "Z9", "A1B"]
        
        for code in valid_codes:
            member = Member(nome="Test", cognome="User", q0=code)
            self.assertEqual(member.q0, code)
    
    def test_quota_normalization(self):
        """Test that quota codes are normalized to uppercase."""
        member = Member(nome="Test", cognome="User", q0="aa")
        self.assertEqual(member.q0, "AA")
    
    def test_invalid_quota_length(self):
        """Test invalid quota code length."""
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", q0="ABCD")  # Too long
    
    def test_invalid_quota_chars(self):
        """Test invalid characters in quota codes."""
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", q0="A!")
    
    def test_empty_quota_allowed(self):
        """Test that empty quota codes are allowed."""
        member = Member(nome="Test", cognome="User", q0="")
        self.assertEqual(member.q0, "")


class TestSocioField(unittest.TestCase):
    """Test socio type validation."""

    def test_valid_socio_values(self):
        """Accepted socio values should be normalized to uppercase."""
        for value in ["ham", "RCL", "thr", "ord"]:
            member = Member(nome="Test", cognome="User", socio=value)
            self.assertIn(member.socio, {"HAM", "RCL", "THR", "ORD"})

    def test_invalid_socio_value(self):
        """Invalid socio values should raise an error."""
        with self.assertRaises(InvalidFormatError):
            Member(nome="Test", cognome="User", socio="VIP")


class TestMemberSerialization(unittest.TestCase):
    """Test Member to_dict and from_dict methods."""
    
    def test_to_dict(self):
        """Test converting member to dictionary."""
        member = Member(
            nome="Mario",
            cognome="Rossi",
            email="mario@example.com",
            attivo=True
        )
        
        data = member.to_dict()
        
        self.assertEqual(data['nome'], "Mario")
        self.assertEqual(data['cognome'], "Rossi")
        self.assertEqual(data['email'], "mario@example.com")
        self.assertEqual(data['attivo'], 1)  # Boolean converted to int
    
    def test_from_dict(self):
        """Test creating member from dictionary."""
        data: dict[str, str | int] = {
            'id': 1,
            'nome': 'Mario',
            'cognome': 'Rossi',
            'email': 'mario@example.com',
            'attivo': 1  # Int from database
        }
        
        member = Member.from_dict(data)  # type: ignore[arg-type]
        
        self.assertEqual(member.id, 1)
        self.assertEqual(member.nome, "Mario")
        self.assertEqual(member.cognome, "Rossi")
        self.assertEqual(member.email, "mario@example.com")
        self.assertEqual(member.attivo, True)  # Int converted to boolean
    
    def test_roundtrip_serialization(self):
        """Test that to_dict -> from_dict preserves data."""
        original = Member(
            nome="Mario",
            cognome="Rossi",
            email="mario@example.com",
            codicefiscale="RSSMRA80A01H501U",
            attivo=True
        )
        
        data = original.to_dict()
        restored = Member.from_dict(data)  # type: ignore[arg-type]
        
        self.assertEqual(original.nome, restored.nome)
        self.assertEqual(original.cognome, restored.cognome)
        self.assertEqual(original.email, restored.email)
        self.assertEqual(original.codicefiscale, restored.codicefiscale)
        self.assertEqual(original.attivo, restored.attivo)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""
    
    def test_validate_member_data_valid(self):
        """Test validating valid member data."""
        data = {
            'nome': 'Mario',
            'cognome': 'Rossi',
            'email': 'mario@example.com'
        }
        
        # Should not raise any errors
        try:
            validate_member_data(data)
            success = True
        except Exception:
            success = False
        
        self.assertTrue(success)

    def test_sanitize_member_input_socio(self):
        """sanitize_member_input should normalize socio values."""
        data = {'socio': 'ham'}
        sanitized = sanitize_member_input(data)
        self.assertEqual(sanitized['socio'], 'HAM')
    
    def test_validate_member_data_invalid(self):
        """Test validating invalid member data."""
        data = {
            'nome': '',  # Empty nome
            'cognome': 'Rossi'
        }
        
        with self.assertRaises(RequiredFieldError):
            validate_member_data(data)
    
    def test_sanitize_member_input(self):
        """Test sanitizing member input."""
        data = {
            'nome': '  Mario  ',
            'cognome': '  Rossi  ',
            'email': ' MARIO@EXAMPLE.COM ',
            'codicefiscale': ' rssmra80a01h501u '
        }
        
        sanitized = sanitize_member_input(data)
        
        self.assertEqual(sanitized['nome'], 'Mario')
        self.assertEqual(sanitized['cognome'], 'Rossi')
        self.assertEqual(sanitized['email'], 'mario@example.com')  # Normalized to lowercase
        self.assertEqual(sanitized['codicefiscale'], 'RSSMRA80A01H501U')  # Normalized to uppercase
    
    def test_sanitize_handles_none(self):
        """Test that sanitize handles None values."""
        data = {
            'nome': 'Mario',
            'cognome': 'Rossi',
            'email': None
        }
        
        sanitized = sanitize_member_input(data)
        
        self.assertEqual(sanitized['nome'], 'Mario')
        self.assertIsNone(sanitized['email'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
