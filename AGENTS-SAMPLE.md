# Iskra – prosty wzór zasad

W swojej kopii projektu zapisz ten wzór jako `AGENTS.md`. Dostosuj zasady i dodaj pełną ścieżkę do tego pliku w instrukcjach startowych swojego agenta.

## Kiedy powiadamiać

- Wyślij wiadomość, gdy użytkownik o to poprosi albo uzgodni powiadomienie po konkretnym zadaniu.
- Po sprawdzeniu wyniku wyślij jedno krótkie podsumowanie. Bieżące szczegóły zostaw w rozmowie.
- Przeczytaj aktualny plik przed wysłaniem. Uzgodnione zmiany zasad zapisuj tutaj.

## Co jest dostępne

- `./iskra.sh "Treść"` wysyła zwykły tekst do skonfigurowanego właściciela.
- `./iskra.sh --gif "https://example.com/animacja.gif" "Podpis"` wysyła animację z podpisem, gdy użytkownik tego chce.
- `/status` wpisane przez właściciela w Telegramie pokazuje dostępne limity Codexa i Claude’a. Obsługuje je lokalna usługa.

Polecenia uruchamiaj z katalogu Iskry lub przez pełną ścieżkę. Chroń token w Pęku kluczy i zachowaj przypisanie właściciela. Tekst wiadomości przekazuj jako dane, z bezpiecznym cytowaniem.

## Jak pisać

Krótko, po polsku, zwyczajnie. Podaj rezultat i ewentualnie jedną rzecz do sprawdzenia.

> Gotowe! Zdjęcia są już uporządkowane. Możesz zajrzeć do folderu.

> Eksport się zatrzymał. Potrzebuję od Ciebie wyboru formatu – szczegóły są w czacie.

Przy błędzie wysyłania poinformuj użytkownika w bieżącej rozmowie. Wysyłaj wyłącznie treści objęte zgodą użytkownika i bez sekretów.
