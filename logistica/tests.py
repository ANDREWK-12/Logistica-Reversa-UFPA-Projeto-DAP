from django.test import TestCase
from .models import MaterialDescarte


class DashboardTests(TestCase):
    def setUp(self):
        MaterialDescarte.objects.create(
            unidade='ICEN',
            categoria='toner',
            modelo='Toner A',
            quantidade=3,
        )
        MaterialDescarte.objects.create(
            unidade='ICEN',
            categoria='toner',
            modelo='Toner B',
            quantidade=4,
        )
        MaterialDescarte.objects.create(
            unidade='ICEN',
            categoria='pilha',
            modelo='Pilha AA',
            quantidade=2,
        )
        MaterialDescarte.objects.create(
            unidade='ICED',
            categoria='toner',
            modelo='Toner C',
            quantidade=5,
        )

    def test_categories_are_aggregated_by_category(self):
        response = self.client.get('/painel-restrito-ufpa/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cat_labels'], ['Pilha', 'Toner'])
        self.assertEqual(response.context['cat_data'], [2, 12])

    def test_category_and_unit_filters_are_applied_to_dashboard(self):
        response = self.client.get(
            '/painel-restrito-ufpa/',
            {'categoria': 'toner', 'unidade': 'ICEN'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['categoria_filtro'], 'toner')
        self.assertEqual(response.context['cat_labels'], ['Toner'])
        self.assertEqual(response.context['cat_data'], [7])
        self.assertEqual(response.context['total_itens'], 7)
        self.assertEqual(response.context['total_unidades'], 1)
        self.assertEqual(response.context['descartes'].count(), 2)


class RegistroRelatorioTests(TestCase):
    def test_finalizar_registro_returns_pdf_for_entire_temporary_list(self):
        session = self.client.session
        session['lista_materiais'] = [
            {
                'unidade': 'ICEN',
                'categoria': 'toner',
                'categoria_exibicao': 'Toner',
                'modelo': 'Toner A',
                'quantidade': 3,
            },
            {
                'unidade': 'ICEN',
                'categoria': 'pilha',
                'categoria_exibicao': 'Pilha',
                'modelo': 'Pilha AA',
                'quantidade': 2,
            },
        ]
        session.save()

        response = self.client.post(
            '/registrar/',
            {'finalizar_registro': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertEqual(MaterialDescarte.objects.count(), 2)
        self.assertEqual(self.client.session['lista_materiais'], [])
