# Iskra – prywatny bot Telegrama

[![Claude Code](https://img.shields.io/badge/Claude_Code-supported-D97757?logo=claude&logoColor=white)](https://code.claude.com/docs/en/quickstart) [![Codex](https://img.shields.io/badge/Codex-supported-000000)](https://learn.chatgpt.com/docs/cli) [![macOS](https://img.shields.io/badge/macOS-only-000000?logo=apple&logoColor=white)](https://www.apple.com/macos/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

[English](README.md) · **Polski**

Iskra wysyła krótkie powiadomienia od agentów. Komenda `/status` pokazuje limity Codexa i/lub Claude’a, pozostałe procenty oraz terminy resetu. Działa lokalnie na Macu, bez wywoływania modeli przy obsłudze tej komendy.

## Uruchomienie na swoim Macu

Potrzebujesz Telegrama, Pęku kluczy, curl, Pythona 3.9+ oraz zainstalowanego i zalogowanego CLI Codexa i/lub Claude Code. `/status` pokazuje tylko te, których używasz. Sprawdź `python3 --version` oraz `codex --version` i/lub `claude auth status`. Instalatory są na stronach [Python](https://www.python.org/downloads/macos/), [Codex](https://learn.chatgpt.com/docs/cli) i [Claude Code](https://code.claude.com/docs/en/quickstart). Limity wymagają logowania do kont z subskrypcją.

1. Umieść ten katalog w stałym miejscu. Otwórz Terminal w tym katalogu.
2. W Telegramie otwórz oficjalnego `@BotFather`, wyślij `/newbot` i utwórz własnego bota. Zachowaj otrzymany token dla siebie.
3. W aplikacji **Dostęp do pęku kluczy** dodaj element hasła do pęku „login”. Jako nazwę wpisz dokładnie `Iskra - Telegram Bot` – po niej Iskra znajduje token. Jako konto wpisz nazwę swojego bota (konto to tylko opis). Jako hasło wklej token. Trzymaj na Macu jeden taki wpis.
4. Wyślij `/start` do swojego nowego bota. Przed konfiguracją zachowaj jego nazwę dla siebie. Następnie wykonaj poniższe polecenia. Jeśli macOS zapyta o dostęp do odpowiedniego wpisu Pęku kluczy, zaakceptuj go.

```sh
chmod 700 iskra.sh
./iskra.sh setup
./iskra.sh "Hej, Iskra działa!"
python3 listener.py status
python3 listener.py install
```

`setup` zapisuje identyfikator ostatniej prywatnej rozmowy i blokuje ponowną konfigurację. Wiadomość testowa powinna dotrzeć do Ciebie. Po instalacji wyślij `/status` do swojego bota. Pierwsze uruchomienie odbiornika pomija wcześniejsze wiadomości.

Jeżeli `codex` działa tylko w aplikacji, podaj ścieżkę do jego pliku wykonywalnego w obu poleceniach Pythona, np. `python3 listener.py --codex "/pełna/ścieżka/do/codex" install`. Instalacja usługi zapamiętuje podaną ścieżkę.

## Codzienne używanie

- W Telegramie wysyłasz `/status`. Odpowiedź jest po angielsku, wąskim blokiem monospace. Paski pokazują pozostały limit. Reset zawiera skrót dnia tygodnia i datę bez roku lub `today` / `tomorrow`. Stopka `Updated` oznacza czas odczytu danych. Godziny są w strefie czasowej Twojego Maca.
- Agent może wysłać tekst przez `./iskra.sh "Gotowe. Możesz sprawdzić wynik."` albo animację przez `./iskra.sh --gif "https://example.com/animacja.gif" "Gotowe!"`.
- Usługa startuje przy logowaniu. Dane mają pamięć podręczną 60 s, a odstęp między odpowiedziami wynosi co najmniej 10 s.

Skopiuj **[AGENTS-SAMPLE.md](AGENTS-SAMPLE.md)** jako `AGENTS.md` i dostosuj do swoich zasad. `AGENTS.md` zostaje lokalnie i Git go pomija. Koordynator powinien czytać aktualny plik przed powiadomieniem – dodaj odwołanie z pełną ścieżką w jego instrukcjach startowych. Zapis zasad sam nie uruchamia agentów.

## Zatrzymanie i przenoszenie

```sh
launchctl bootout "gui/$(id -u)/app.iskra.telegram-status"
```

Po zmianie nazwy lub przeniesieniu katalogu uruchom ponownie `python3 listener.py install` i popraw odwołania w instrukcjach agentów. To samo polecenie ponownie włącza zatrzymaną usługę.

Konfiguracja i log są w `~/.config/iskra/`, a wpis usługi w `~/Library/LaunchAgents/app.iskra.telegram-status.plist`. Dane kont i tokeny są pobierane lokalnie. **Udostępniaj tylko repozytorium**, nigdy swojego `AGENTS.md`, konfiguracji ani tokenów. Każdy konfiguruje swojego bota i logowania na swoim Macu.

## Gdy coś nie działa

Sprawdź `~/.config/iskra/listener.log`. Odbiornik odpowiada tylko na `/status` właściciela w zapisanej prywatnej rozmowie. Odrzuca obcych nadawców, grupy, przekazane wiadomości i komendy starsze niż 2 min. Po błędzie wyślij świeżą komendę. Zapis postępu zapobiega ponownemu obsłużeniu tej samej wiadomości, ale przerwane wysyłanie może wymagać ponowienia komendy.

Przy niedostępnych limitach Claude’a odśwież logowanie przez `claude` → `/login`. Codex korzysta z App Server `account/rateLimits/read`.

Testy lokalne uruchomisz przez `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_listener.py`. Składnię skryptu sprawdza `bash -n iskra.sh`.

## Jeden bot na osobę

Każda osoba tworzy własnego bota. Nie udostępniaj swojego tokena – kto go ma, w pełni steruje botem. Dwie kopie Iskry na jednym bocie też by się kłóciły, bo Telegram oddaje każdą wiadomość tylko jednemu odbiorcy.

Inni mogą napisać do Twojego bota, ale Iskra odpowiada tylko właścicielowi zapisanemu przy `setup`.

Nazwy się nie mieszają. Nazwa bota w Telegramie (`@…_bot`) jest unikalna na całym świecie, więc BotFather sam każe wybrać wolną. Wpis w Pęku kluczy jest lokalny na Twoim Macu, więc każdy używa tej samej nazwy `Iskra - Telegram Bot`.

## Znane ograniczenia

- Limity Claude’a pochodzą z nieudokumentowanego endpointu, z którego korzysta Claude Code. Aktualizacja może go zepsuć.
- Na razie przetestowane na jednym Macu.
- Mac musi być wybudzony, online i zalogowany.

## Współtworzenie

Wkład mile widziany – śmiało zgłaszaj issue albo pull request. Port na Linuksa też: specyficzne dla macOS są Pęk kluczy, dane logowania Claude Code i usługa launchd.

## Autor i licencja

[Adam Sarba](https://github.com/adamsarba) · licencja [MIT](LICENSE)
