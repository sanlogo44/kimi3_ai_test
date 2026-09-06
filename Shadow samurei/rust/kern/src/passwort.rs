//! Passwort-Hashes im Format von Werkzeug.
//!
//! Damit Weboberfläche (Rust) und Desktop-Oberfläche (Python) dieselbe
//! Datei `data/users.json` nutzen können, wird genau das Format von
//! `werkzeug.security` erzeugt und geprüft:
//!
//! * `scrypt:n:r:p$salz$hex` – Standard neuerer Werkzeug-Fassungen,
//! * `pbkdf2:sha256:runden$salz$hex` – Format älterer Fassungen.
//!
//! Der Vergleich der Hashes läuft zeitunabhängig (`subtle`).

use rand::Rng;
use sha2::Sha256;
use subtle::ConstantTimeEq;

/// Länge des abgeleiteten Schlüssels bei `scrypt` (wie bei Werkzeug).
const SCRYPT_LAENGE: usize = 64;
/// Standardparameter von Werkzeug für `scrypt`.
const SCRYPT_N: u32 = 32768;
const SCRYPT_R: u32 = 8;
const SCRYPT_P: u32 = 1;
/// Länge des Salzes in Zeichen (wie bei Werkzeug).
const SALZ_LAENGE: usize = 16;
/// Zeichenvorrat des Salzes (wie bei Werkzeug: Buchstaben und Ziffern).
const SALZ_ZEICHEN: &[u8] = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

/// Erzeugt ein zufälliges Salz.
fn salz() -> String {
    let mut zufall = rand::thread_rng();
    (0..SALZ_LAENGE)
        .map(|_| SALZ_ZEICHEN[zufall.gen_range(0..SALZ_ZEICHEN.len())] as char)
        .collect()
}

/// Berechnet den `scrypt`-Hash eines Passworts.
fn scrypt_hash(passwort: &str, salz: &str, n: u32, r: u32, p: u32) -> Option<String> {
    let log_n = (n as f64).log2().round() as u8;
    if 2u64.pow(log_n as u32) != n as u64 {
        return None;
    }
    let parameter = scrypt::Params::new(log_n, r, p, SCRYPT_LAENGE).ok()?;
    let mut ausgabe = vec![0u8; SCRYPT_LAENGE];
    scrypt::scrypt(passwort.as_bytes(), salz.as_bytes(), &parameter, &mut ausgabe).ok()?;
    Some(hex::encode(ausgabe))
}

/// Berechnet den `pbkdf2`-Hash eines Passworts (SHA-256).
fn pbkdf2_hash(passwort: &str, salz: &str, runden: u32) -> String {
    let mut ausgabe = [0u8; 32];
    pbkdf2::pbkdf2_hmac::<Sha256>(passwort.as_bytes(), salz.as_bytes(), runden, &mut ausgabe);
    hex::encode(ausgabe)
}

/// Erzeugt einen Passwort-Hash im Werkzeug-Format (`scrypt`).
pub fn erzeuge_hash(passwort: &str) -> String {
    let salz = salz();
    match scrypt_hash(passwort, &salz, SCRYPT_N, SCRYPT_R, SCRYPT_P) {
        Some(hash) => format!("scrypt:{SCRYPT_N}:{SCRYPT_R}:{SCRYPT_P}${salz}${hash}"),
        // Sollte nicht vorkommen; dann gilt das ältere, ebenfalls
        // unterstützte Verfahren.
        None => {
            let runden = 1_000_000;
            format!(
                "pbkdf2:sha256:{runden}${salz}${}",
                pbkdf2_hash(passwort, &salz, runden)
            )
        }
    }
}

/// Prüft ein Passwort gegen einen gespeicherten Hash.
///
/// Unbekannte Verfahren und defekte Hashes ergeben `false`.
pub fn pruefe(hash: &str, passwort: &str) -> bool {
    let mut teile = hash.splitn(3, '$');
    let (Some(verfahren), Some(salz), Some(erwartet)) =
        (teile.next(), teile.next(), teile.next())
    else {
        return false;
    };
    let angaben: Vec<&str> = verfahren.split(':').collect();
    let berechnet = match angaben.as_slice() {
        ["scrypt", n, r, p] => {
            let (Ok(n), Ok(r), Ok(p)) = (n.parse::<u32>(), r.parse::<u32>(), p.parse::<u32>())
            else {
                return false;
            };
            match scrypt_hash(passwort, salz, n, r, p) {
                Some(wert) => wert,
                None => return false,
            }
        }
        ["pbkdf2", "sha256", runden] => match runden.parse::<u32>() {
            Ok(runden) => pbkdf2_hash(passwort, salz, runden),
            Err(_) => return false,
        },
        ["pbkdf2", "sha256"] => pbkdf2_hash(passwort, salz, 260_000),
        _ => return false,
    };
    berechnet.as_bytes().ct_eq(erwartet.as_bytes()).into()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn eigener_hash_wird_erkannt() {
        let hash = erzeuge_hash("geheim123");
        assert!(hash.starts_with("scrypt:32768:8:1$"));
        assert!(pruefe(&hash, "geheim123"));
        assert!(!pruefe(&hash, "falsch"));
    }

    #[test]
    fn hash_von_werkzeug_wird_geprueft() {
        // Von „werkzeug.security.generate_password_hash('1234')“ erzeugt.
        let scrypt_hash = "scrypt:32768:8:1$1x3pQmIuOUvtdKFi$65eed30c6df3fdf1abd2bfab23dc634019e91c44d1431ee33bbc6a84fd6bdae232d53f609d36d421543ebea99e2475214cdf5cf3abc04e18a35bb84f9807b22e";
        assert!(pruefe(scrypt_hash, "1234"));
        assert!(!pruefe(scrypt_hash, "12345"));
        // Format älterer Werkzeug-Fassungen.
        let pbkdf2_hash = "pbkdf2:sha256:1000000$GX5byfqQyta97TXC$1678024184e986fb24d9ab787f56c48b3ac2b5fbeeb1e7d9ed3c85125306a4d6";
        assert!(pruefe(pbkdf2_hash, "1234"));
        assert!(!pruefe(pbkdf2_hash, "falsch"));
    }

    #[test]
    fn defekte_hashes_ergeben_false() {
        assert!(!pruefe("", "1234"));
        assert!(!pruefe("ohne-trennzeichen", "1234"));
        assert!(!pruefe("md5$salz$abc", "1234"));
        assert!(!pruefe("scrypt:abc:8:1$salz$abc", "1234"));
        assert!(!pruefe("scrypt:32769:8:1$salz$abc", "1234"));
    }

    #[test]
    fn jedes_salz_ist_neu() {
        assert_ne!(erzeuge_hash("gleich"), erzeuge_hash("gleich"));
    }
}
