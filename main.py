import json
from classes import Person, SpreadsheetParser

def load_config(config_file="config.json"):
        """Load configuration from a JSON file."""
        try:
            with open(config_file, "r") as f:
                return json.load(f), None
        except FileNotFoundError:
            return None, "Configuration file not found."
        except json.JSONDecodeError:
            return None, "Failed to decode JSON from configuration file."

def main():
    people = []
    
    config, error = load_config()
    if config != None:
        for person in config['People']:
            name = person['Name'][0]
            account_numbers = person['Accounts']
            people.append(Person(name, account_numbers))

    parser = SpreadsheetParser('test_transactions.csv', people)
    parser.parse()

if __name__ == "__main__":
    main()
