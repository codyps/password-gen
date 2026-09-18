use rand::{Rng, TryRngCore};
use rand_core::OsRng;

const VOWELS: &[u8] = b"aeiouy";
// no `l`
const CONSONANTS: &[u8] = b"bcdfghjkmnpqrstvwxz";

/// Generate a random password with three hyphen-separated six-character groups.
/// Two groups use consonant-vowel-consonant twice; the third uses CVC+CV with a
/// digit at either end (but never at the start of the password). Exactly one
/// letter is capitalized. Neither `l`, `L`, nor uppercase `O` is used.
///
/// The resulting password is always ascii 20 characters long.
///
/// The format follows [Apple's public reference generator](https://developer.apple.com/password-rules/),
/// except we don't include filtering for "bad" words. If you have a
/// "bad" words matcher, call this function repeatedly until no bad words are
/// found.
#[must_use]
pub fn generate() -> String {
    generate_with_rng(OsRng.unwrap_err())
}

/// Generate a password in the same format as [`generate`], using the supplied RNG.
///
/// See [`generate`] for more information.
///
/// Be sure to pick a secure rng. `rand_core::OsRng`, for example.
#[must_use]
pub fn generate_with_rng<T: rand::CryptoRng + Rng>(mut rng: T) -> String {
    // C = consonant, V = vowel, D = digit. A digit goes before or after
    // a CVC+CV group; it does not replace the first consonant of CVC+CVC.
    const PATTERNS: [&[u8; 20]; 5] = [
        b"cvccvd-cvccvc-cvccvc",
        b"cvccvc-dcvccv-cvccvc",
        b"cvccvc-cvccvd-cvccvc",
        b"cvccvc-cvccvc-dcvccv",
        b"cvccvc-cvccvc-cvccvd",
    ];
    let pattern = PATTERNS[rng.random_range(0..PATTERNS.len())];
    let mut output = pattern.map(|kind| match kind {
        b'c' => CONSONANTS[rng.random_range(0..CONSONANTS.len())],
        b'v' => VOWELS[rng.random_range(0..VOWELS.len())],
        b'd' => b'0' + rng.random_range(0..10u8),
        _ => b'-',
    });

    // Select uniformly among eligible letters, preserving lowercase o while
    // excluding the ambiguous uppercase O. Equivalent to retrying a random
    // letter position whenever it contains o, without an unbounded retry loop.
    let eligible = |c: &u8| c.is_ascii_lowercase() && *c != b'o';
    let count = output.iter().filter(|c| eligible(c)).count();
    let uppercase_index = rng.random_range(0..count);
    output
        .iter_mut()
        .filter(|c| eligible(c))
        .nth(uppercase_index)
        .expect("every pattern contains eligible consonants")
        .make_ascii_uppercase();

    String::from_utf8(output.to_vec()).expect("password alphabet is ASCII")
}
