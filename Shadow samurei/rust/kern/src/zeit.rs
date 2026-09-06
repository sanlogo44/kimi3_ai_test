//! Zeitstempel in genau den Formaten, die die Datendateien verwenden.

use time::format_description::FormatItem;
use time::macros::format_description;
use time::{Duration, OffsetDateTime, PrimitiveDateTime, UtcOffset};

/// ISO-Format der Metrikeinträge, zum Beispiel `2026-09-05T21:30:00`.
const ISO: &[FormatItem<'_>] =
    format_description!("[year]-[month]-[day]T[hour]:[minute]:[second]");
/// Lesbares Format der Bewertungen, zum Beispiel `2026-09-05 21:30:00`.
const LESBAR: &[FormatItem<'_>] =
    format_description!("[year]-[month]-[day] [hour]:[minute]:[second]");
/// Kurzform für Anzeigen, zum Beispiel `05.09. 21:30`.
const KURZ: &[FormatItem<'_>] = format_description!("[day].[month]. [hour]:[minute]");

/// Gibt die aktuelle Ortszeit zurück; ohne Zeitzoneninfo gilt UTC.
pub fn jetzt() -> OffsetDateTime {
    let jetzt = OffsetDateTime::now_utc();
    match UtcOffset::current_local_offset() {
        Ok(abstand) => jetzt.to_offset(abstand),
        Err(_) => jetzt,
    }
}

/// Gibt den aktuellen Zeitpunkt als ISO-Text zurück (`…T…`).
pub fn jetzt_iso() -> String {
    jetzt().format(&ISO).unwrap_or_default()
}

/// Gibt den aktuellen Zeitpunkt als lesbaren Text zurück (mit Leerzeichen).
pub fn jetzt_lesbar() -> String {
    jetzt().format(&LESBAR).unwrap_or_default()
}

/// Wandelt einen gespeicherten Zeitstempel in einen Zeitpunkt um.
///
/// Erkannt werden das ISO-Format, das lesbare Format und ISO-Angaben mit
/// Sekundenbruchteilen. Nicht lesbare Angaben ergeben `None`.
pub fn lese(text: &str) -> Option<PrimitiveDateTime> {
    let gekuerzt: String = text.chars().take(26).collect();
    let ohne_bruchteil = match gekuerzt.split_once('.') {
        Some((vorne, _)) => vorne.to_string(),
        None => gekuerzt,
    };
    PrimitiveDateTime::parse(&ohne_bruchteil, &ISO)
        .or_else(|_| PrimitiveDateTime::parse(&ohne_bruchteil, &LESBAR))
        .ok()
}

/// Gibt eine kurze, lesbare Zeitangabe zurück (`05.09. 21:30`).
///
/// Lässt sich der Text nicht lesen, werden die ersten 16 Zeichen genutzt –
/// genau wie in der bisherigen Python-Fassung.
pub fn kurzzeit(text: &str) -> String {
    match lese(text) {
        Some(zeitpunkt) => zeitpunkt.format(&KURZ).unwrap_or_default(),
        None => text.chars().take(16).collect(),
    }
}

/// Wandelt Unix-Sekunden in einen lesbaren Text der Ortszeit um.
///
/// Wird für den Änderungszeitpunkt der Checkpoint-Dateien genutzt.
pub fn aus_sekunden(sekunden: i64) -> String {
    let Ok(zeitpunkt) = OffsetDateTime::from_unix_timestamp(sekunden) else {
        return String::new();
    };
    let ortszeit = match UtcOffset::current_local_offset() {
        Ok(abstand) => zeitpunkt.to_offset(abstand),
        Err(_) => zeitpunkt,
    };
    ortszeit.format(&LESBAR).unwrap_or_default()
}

/// Gibt den Zeitpunkt vor `tage` Tagen zurück.
pub fn vor_tagen(tage: i64) -> PrimitiveDateTime {
    let grenze = jetzt() - Duration::days(tage.max(0));
    PrimitiveDateTime::new(grenze.date(), grenze.time())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn iso_und_lesbar_haben_die_richtige_laenge() {
        assert_eq!(jetzt_iso().len(), 19);
        assert_eq!(jetzt_lesbar().len(), 19);
        assert!(jetzt_iso().contains('T'));
        assert!(jetzt_lesbar().contains(' '));
    }

    #[test]
    fn beide_formate_werden_gelesen() {
        assert!(lese("2026-09-05T21:30:00").is_some());
        assert!(lese("2026-09-05 21:30:00").is_some());
        assert!(lese("2026-09-05T21:30:00.123456").is_some());
        assert!(lese("kein Datum").is_none());
    }

    #[test]
    fn kurzzeit_kuerzt_sinnvoll() {
        assert_eq!(kurzzeit("2026-09-05T21:30:00"), "05.09. 21:30");
        assert_eq!(kurzzeit("unlesbarer Zeitstempel"), "unlesbarer Zeits");
    }

    #[test]
    fn unix_sekunden_werden_lesbar() {
        let text = aus_sekunden(1_767_225_600);
        assert_eq!(text.len(), 19);
        assert!(text.starts_with("2026-01-01") || text.starts_with("2025-12-31"));
        assert!(aus_sekunden(i64::MAX).is_empty());
    }

    #[test]
    fn vor_tagen_liegt_in_der_vergangenheit() {
        let gerade_jetzt = vor_tagen(0);
        let heute = PrimitiveDateTime::new(jetzt().date(), jetzt().time());
        assert!(vor_tagen(7) < heute);
        assert!(gerade_jetzt <= heute);
    }
}
