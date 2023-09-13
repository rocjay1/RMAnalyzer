from main import *
import unittest

class NonLambdaIntegTest(unittest.TestCase):
    def setUp(self):
        with open("Tests/test_transactions.csv", "r") as f:
            file_content = f.read()
        self.summary = build_summary(file_content, load_config())

    def test_email(self):
        html_body = EmailGenerator.generate_summary_email(self.summary)
        result_string = """<html><head></head><body><h1>Summary for 09/23:</h1>
<table border='1'>
<thead>
<tr>
<th>Dining & Drinks</th>
<th>Groceries</th>
<th>Entertainment & Rec.</th>
<th><strong>Total</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td>Rocco</td>
<td>148.58</td>
<td>0</td>
<td>0</td>
<td>148.58</td>
</tr>
<tr>
<td>Tori</td>
<td>0</td>
<td>0</td>
<td>0</td>
<td>0</td>
</tr>
<tr>
<td>Diff (Rocco - Tori)</td>
<td>148.58</td>
<td>0</td>
<td>0</td>
<td>148.58</td>
</tr>
</tbody>
</table>
</body>
</html>"""
        self.assertEqual(html_body, result_string)


def main():
    unittest.main()

if __name__ == "__main__":
    main()
