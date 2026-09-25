from __future__ import annotations

import base64
import unittest
from unittest.mock import MagicMock, call, patch

from agent_local_v1.app.services import odoo_service
from agent_local_v1.app import human_validation_store


class OdooServiceTests(unittest.TestCase):
    def test_export_invoice_builds_expected_xmlrpc_calls(self) -> None:
        common = MagicMock()
        common.authenticate.return_value = 7
        models = MagicMock()
        models.execute_kw.side_effect = [
            [{"company_id": [1, "My Company"], "company_ids": [1]}],
            [{"id": 1, "name": "EUR"}],
            [],
            42,
            [{"id": 5, "name": "TVA 20% achats", "amount": 20.0}],
            99,
            123,
        ]

        with (
            patch.object(odoo_service, "ODOO_MOCK_MODE", False),
            patch.object(odoo_service, "ODOO_URL", "http://localhost:8069"),
            patch.object(odoo_service, "ODOO_DB", "keymanage_db"),
            patch.object(odoo_service, "ODOO_USERNAME", "admin@example.com"),
            patch.object(odoo_service, "ODOO_PASSWORD", "admin"),
            patch.object(
                odoo_service.xmlrpc_client,
                "ServerProxy",
                side_effect=[common, models],
            ) as server_proxy,
        ):
            result = odoo_service.export_invoice_to_odoo(
                {
                    "supplier": "ORANGE",
                    "supplier_siret": "38012986600018",
                    "invoice_number": "FA-2026-0042",
                    "invoice_date": "21/08/2026",
                    "lines": [
                        {"description": "Abonnement téléphonique", "amount_ht": 29.99, "amount_ttc": 35.99, "tva": 20},
                        {"label": "Fibre professionnelle", "total_net": 50, "total_gross": 60, "vat_percent": 20},
                    ],
                    "pdf_bytes": b"%PDF-1.7 test",
                    "pdf_filename": "FA-2026-0042.pdf",
                }
            )

        self.assertEqual(result["move_id"], 99)
        self.assertEqual(result["partner_id"], 42)
        self.assertEqual(result["attachment_id"], 123)
        self.assertTrue(result["attachment_created"])
        self.assertIsNone(result["attachment_error"])
        self.assertEqual(
            server_proxy.call_args_list,
            [
                call("http://localhost:8069/xmlrpc/2/common", allow_none=True),
                call("http://localhost:8069/xmlrpc/2/object", allow_none=True),
            ],
        )
        common.authenticate.assert_called_once_with(
            "keymanage_db",
            "admin@example.com",
            "admin",
            {},
        )

        company_call, currency_call, search_call, partner_create_call, tax_call, move_create_call, attachment_create_call = (
            models.execute_kw.call_args_list
        )
        self.assertEqual(company_call.args[3:5], ("res.users", "read"))
        self.assertEqual(currency_call.args[3:5], ("res.currency", "search_read"))
        self.assertEqual(search_call.args[3:5], ("res.partner", "search_read"))
        self.assertEqual(partner_create_call.args[3:5], ("res.partner", "create"))
        self.assertEqual(tax_call.args[3:5], ("account.tax", "search_read"))
        self.assertEqual(
            tax_call.args[5][0],
            [("type_tax_use", "=", "purchase"), ("amount", "=", 20.0)],
        )

        self.assertEqual(move_create_call.args[3:5], ("account.move", "create"))
        move_values = move_create_call.args[5][0]
        self.assertEqual(move_values["move_type"], "in_invoice")
        self.assertEqual(move_values["partner_id"], 42)
        self.assertEqual(move_values["currency_id"], 1)
        self.assertEqual(move_values["ref"], "FA-2026-0042")
        self.assertEqual(move_values["invoice_date"], "2026-08-21")
        self.assertEqual(
            move_values["invoice_line_ids"],
            [
                (0, 0, {"name": "Abonnement téléphonique", "price_unit": 29.99, "quantity": 1.0, "tax_ids": [(6, 0, [5])]}),
                (0, 0, {"name": "Fibre professionnelle", "price_unit": 50.0, "quantity": 1.0, "tax_ids": [(6, 0, [5])]}),
            ],
        )

        self.assertEqual(attachment_create_call.args[3:5], ("ir.attachment", "create"))
        attachment_values = attachment_create_call.args[5][0]
        self.assertEqual(attachment_values["res_model"], "account.move")
        self.assertEqual(attachment_values["res_id"], 99)
        self.assertEqual(attachment_values["mimetype"], "application/pdf")
        self.assertEqual(
            attachment_values["datas"],
            base64.b64encode(b"%PDF-1.7 test").decode("ascii"),
        )

    def test_get_or_create_partner_reuses_existing_partner(self) -> None:
        common = MagicMock()
        common.authenticate.return_value = 7
        models = MagicMock()
        models.execute_kw.return_value = [{"id": 88, "name": "METRO FRANCE", "vat": "FR123"}]

        with (
            patch.object(odoo_service, "ODOO_MOCK_MODE", False),
            patch.object(odoo_service, "ODOO_USERNAME", "admin@example.com"),
            patch.object(odoo_service, "ODOO_PASSWORD", "admin"),
            patch.object(odoo_service.xmlrpc_client, "ServerProxy", side_effect=[common, models]),
        ):
            partner_id = odoo_service.get_or_create_partner("METRO FRANCE", "FR123")

        self.assertEqual(partner_id, 88)
        self.assertEqual(models.execute_kw.call_count, 1)

    def test_missing_purchase_tax_adds_vat_fallback_line(self) -> None:
        common = MagicMock()
        common.authenticate.return_value = 7
        models = MagicMock()
        models.execute_kw.side_effect = [
            [{"company_id": [1, "My Company"], "company_ids": [1]}],
            [{"id": 1, "name": "EUR"}],
            [{"id": 88, "name": "FOURNISSEUR", "vat": False}],
            [],
            501,
        ]

        with (
            patch.object(odoo_service, "ODOO_MOCK_MODE", False),
            patch.object(odoo_service, "ODOO_USERNAME", "admin@example.com"),
            patch.object(odoo_service, "ODOO_PASSWORD", "admin"),
            patch.object(odoo_service.xmlrpc_client, "ServerProxy", side_effect=[common, models]),
        ):
            result = odoo_service.export_invoice_to_odoo(
                {
                    "supplier": "FOURNISSEUR",
                    "lines": [
                        {"description": "Prestation", "amount_ht": 100, "amount_ttc": 120, "tva": 20}
                    ],
                }
            )

        self.assertEqual(result["move_id"], 501)
        move_values = models.execute_kw.call_args_list[4].args[5][0]
        self.assertEqual(move_values["currency_id"], 1)
        self.assertEqual(
            move_values["invoice_line_ids"],
            [
                (0, 0, {"name": "Prestation", "price_unit": 100.0, "quantity": 1.0}),
                (0, 0, {"name": "TVA 20% — taxe d'achat Odoo introuvable", "price_unit": 20.0, "quantity": 1.0}),
            ],
        )

    def test_corrected_account_is_used_as_odoo_account_id(self) -> None:
        common = MagicMock()
        common.authenticate.return_value = 7
        models = MagicMock()
        models.execute_kw.side_effect = [
            [{"company_id": [1, "My Company"], "company_ids": [1]}],
            [{"id": 1, "name": "EUR"}],
            [{"id": 88, "name": "ASSAINIS", "vat": False}],
            [{"id": 77, "code": "613310", "name": "Entretien et réparations des biens immobiliers", "company_id": [1, "My Company"]}],
            501,
        ]

        with (
            patch.object(odoo_service, "ODOO_MOCK_MODE", False),
            patch.object(odoo_service, "ODOO_USERNAME", "admin@example.com"),
            patch.object(odoo_service, "ODOO_PASSWORD", "admin"),
            patch.object(odoo_service, "ODOO_ACCOUNT_CODE_MAP", {"6152": "613310", "6155": "613320"}),
            patch.object(odoo_service.xmlrpc_client, "ServerProxy", side_effect=[common, models]),
        ):
            result = odoo_service.export_invoice_to_odoo(
                {
                    "supplier": "ASSAINIS",
                    "lines": [
                        {
                            "description": "Pompage",
                            "amount_ht": 800,
                            "recommended_account": "6062",
                            "corrected_account": "6152",
                            "human_validation_result": {
                                "action": "correct_account",
                                "corrected_account": "6152",
                            },
                        }
                    ],
                }
            )

        account_call = models.execute_kw.call_args_list[3]
        self.assertEqual(account_call.args[3:5], ("account.account", "search_read"))
        self.assertEqual(
            account_call.args[5][0],
            [("code", "=", "613310"), ("company_id", "=", 1)],
        )
        move_values = models.execute_kw.call_args_list[4].args[5][0]
        self.assertEqual(move_values["invoice_line_ids"][0][2]["account_id"], 77)
        self.assertEqual(result["account_resolutions"][0]["account_code"], "6152")
        self.assertEqual(result["account_resolutions"][0]["odoo_account_code"], "613310")
        self.assertEqual(result["account_resolutions"][0]["account_id"], 77)

    def test_missing_account_does_not_block_invoice_creation(self) -> None:
        common = MagicMock()
        common.authenticate.return_value = 7
        models = MagicMock()
        models.execute_kw.side_effect = [
            [{"company_id": [1, "My Company"], "company_ids": [1]}],
            [{"id": 1, "name": "EUR"}],
            [{"id": 88, "name": "FOURNISSEUR", "vat": False}],
            502,
        ]

        with (
            patch.object(odoo_service, "ODOO_MOCK_MODE", False),
            patch.object(odoo_service, "ODOO_USERNAME", "admin@example.com"),
            patch.object(odoo_service, "ODOO_PASSWORD", "admin"),
            patch.object(odoo_service, "ODOO_ACCOUNT_CODE_MAP", {"6152": "613310", "6155": "613320"}),
            patch.object(odoo_service.xmlrpc_client, "ServerProxy", side_effect=[common, models]),
        ):
            result = odoo_service.export_invoice_to_odoo(
                {
                    "supplier": "FOURNISSEUR",
                    "lines": [
                        {"description": "Article", "amount_ht": 10, "recommended_account": "6011"}
                    ],
                }
            )

        move_values = models.execute_kw.call_args_list[3].args[5][0]
        self.assertNotIn("account_id", move_values["invoice_line_ids"][0][2])
        self.assertFalse(result["account_resolutions"][0]["found"])
        self.assertFalse(result["account_resolutions"][0]["mapping_found"])
        self.assertEqual(result["unmapped_account_codes"], ["6011"])
        self.assertEqual(result["move_id"], 502)

    def test_mapped_odoo_account_missing_does_not_block_invoice_creation(self) -> None:
        common = MagicMock()
        common.authenticate.return_value = 7
        models = MagicMock()
        models.execute_kw.side_effect = [
            [{"company_id": [1, "My Company"], "company_ids": [1]}],
            [{"id": 1, "name": "EUR"}],
            [{"id": 88, "name": "FOURNISSEUR", "vat": False}],
            [],
            504,
        ]

        with (
            patch.object(odoo_service, "ODOO_MOCK_MODE", False),
            patch.object(odoo_service, "ODOO_USERNAME", "admin@example.com"),
            patch.object(odoo_service, "ODOO_PASSWORD", "admin"),
            patch.object(odoo_service, "ODOO_ACCOUNT_CODE_MAP", {"6155": "613320"}),
            patch.object(odoo_service.xmlrpc_client, "ServerProxy", side_effect=[common, models]),
        ):
            result = odoo_service.export_invoice_to_odoo(
                {
                    "supplier": "FOURNISSEUR",
                    "lines": [
                        {"description": "Entretien mobilier", "amount_ht": 50, "recommended_account": "6155"}
                    ],
                }
            )

        account_call = models.execute_kw.call_args_list[3]
        self.assertEqual(
            account_call.args[5][0],
            [("code", "=", "613320"), ("company_id", "=", 1)],
        )
        move_values = models.execute_kw.call_args_list[4].args[5][0]
        self.assertNotIn("account_id", move_values["invoice_line_ids"][0][2])
        self.assertEqual(result["missing_account_codes"], ["6155"])
        self.assertEqual(result["unmapped_account_codes"], [])
        self.assertEqual(result["move_id"], 504)

    def test_attachment_failure_does_not_hide_created_invoice(self) -> None:
        common = MagicMock()
        common.authenticate.return_value = 7
        models = MagicMock()
        models.execute_kw.side_effect = [
            [{"company_id": [1, "My Company"], "company_ids": [1]}],
            [{"id": 1, "name": "EUR"}],
            [{"id": 88, "name": "FOURNISSEUR", "vat": False}],
            503,
            odoo_service.xmlrpc_client.Fault(1, "attachment denied"),
        ]

        with (
            patch.object(odoo_service, "ODOO_MOCK_MODE", False),
            patch.object(odoo_service, "ODOO_USERNAME", "admin@example.com"),
            patch.object(odoo_service, "ODOO_PASSWORD", "admin"),
            patch.object(odoo_service.xmlrpc_client, "ServerProxy", side_effect=[common, models]),
        ):
            result = odoo_service.export_invoice_to_odoo(
                {
                    "supplier": "FOURNISSEUR",
                    "lines": [{"description": "Article", "amount_ht": 10}],
                    "pdf_bytes": b"%PDF-1.7 test",
                    "pdf_filename": "facture.pdf",
                }
            )

        self.assertEqual(result["move_id"], 503)
        self.assertIsNone(result["attachment_id"])
        self.assertFalse(result["attachment_created"])
        self.assertIn("attachment denied", result["attachment_error"])

    def test_export_tracking_preserves_legacy_database_history(self) -> None:
        items = [
            {
                "invoice_id": "invoice-1",
                "odoo_move_id": 2,
                "odoo_exported_at": "2025-10-31T00:00:00+00:00",
            }
        ]
        written_items = []

        with (
            patch.object(human_validation_store, "_read_items_unlocked", return_value=items),
            patch.object(
                human_validation_store,
                "_write_items_unlocked",
                side_effect=lambda value: written_items.extend(value),
            ),
        ):
            updated = human_validation_store.mark_invoice_exported_to_odoo(
                "invoice-1",
                7,
                "keymanage_fr",
            )

        self.assertEqual(updated, 1)
        self.assertEqual(written_items[0]["odoo_move_id"], 7)
        self.assertEqual(written_items[0]["odoo_database"], "keymanage_fr")
        self.assertEqual(
            [(entry["database"], entry["move_id"]) for entry in written_items[0]["odoo_exports"]],
            [("keymanage_db", 2), ("keymanage_fr", 7)],
        )


if __name__ == "__main__":
    unittest.main()
