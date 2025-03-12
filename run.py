import dotenv

from bot import Client

def main():
    client = Client() # bot client
    client.run(dotenv.get_key(dotenv.find_dotenv(), 'client_secret')) # start bot client

if __name__ == '__main__':
    main()