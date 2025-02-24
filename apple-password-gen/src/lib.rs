use rand::{Rng, TryRngCore};
use rand_core::OsRng;

const VOWELS: &'static [u8] = b"aeiouy";
// no `l`
const CONSONANTS: &'static [u8] = b"bcdfghjkmnpqrstvwxz";

/// Generate a random password in the form of `cvccvc-cvccvc-cvccvc`, with 1
/// capital and 1 number replacing a letter. No `L` is used in the password.
///
/// The resulting password is always ascii 20 characters long.
///
/// The format matches the passwords generated by Apple's Strong Password
/// Suggestion, except we don't include filtering for "bad" words. If you have a
/// "bad" words matcher, call this function repeatedly until no bad words are
/// found.
#[must_use]
pub fn generate() -> String {
    generate_with_rng(OsRng.unwrap_err())
}

/// Generate a random password in the form of `cvccvc-cvccvc-cvccvc`, with 1
/// capital and 1 number replacing a letter. Use a sepecific Rng to do so.
///
/// See [`generate`] for more information.
///
/// Be sure to pick a secure rng. `rand_core::OsRng`, for example.
#[must_use]
pub fn generate_with_rng<T: rand::CryptoRng + Rng>(mut rng: T) -> String {
    assert_eq!(VOWELS.len(), 6);
    assert_eq!(CONSONANTS.len(), 19);

    // vessIK-dowbec-ferzi6
    // govwun-disMad-8wasde
    // seppem-nothis-kopbI4
    // zogxuf-xubFat-kyassa8
    // vabTog-ciwfig-7zunfy
    // kijzy4-cijhiz-pecguG
    // mupvaz-1qyzru-vAxfex
    // gYcmi4-misbyh-zobpin
    // zertun-togba2-kijruH
    let pattern_cv = b"cvccvc-cvccvc-cvccvc";
    let pattern_nu = b".....1.1....1.1....1";

    let number_pos_ct = pattern_nu
        .iter()
        .fold(0usize, |acc, &c| if c == b'1' { acc + 1 } else { acc });

    let letter_pos_ct =
        pattern_cv.iter().fold(
            0usize,
            |acc, &c| if c == b'c' || c == b'v' { acc + 1 } else { acc },
        ) - 1;

    // pick number position. The number replaces a potential letter
    let mut number_i = rng.random_range(0..number_pos_ct);
    let mut number_pos = None;
    for (i, p) in pattern_nu.iter().enumerate() {
        if *p == b'1' {
            if number_i == 0 {
                number_pos = Some(i);
                break;
            }
            number_i -= 1;
        }
    }
    let number_pos = number_pos.unwrap();

    // pick upper-case position. This modifies a chosen letter
    let uppercase_pos = rng.random_range(0..letter_pos_ct);

    let mut output = String::with_capacity(pattern_cv.len());

    // fill in letters
    let mut letter_pos = 0;
    for (i, p) in pattern_cv.iter().enumerate() {
        if i == number_pos {
            output.push_str(&format!("{}", rng.random_range(0..10)));
        } else {
            match *p {
                b'c' => {
                    if letter_pos == uppercase_pos {
                        output.push(
                            CONSONANTS[rng.random_range(0..CONSONANTS.len())].to_ascii_uppercase()
                                as char,
                        );
                    } else {
                        output.push(CONSONANTS[rng.random_range(0..CONSONANTS.len())] as char);
                    }
                    letter_pos += 1;
                }
                b'v' => {
                    if letter_pos == uppercase_pos {
                        output.push(
                            VOWELS[rng.random_range(0..VOWELS.len())].to_ascii_uppercase() as char,
                        );
                    } else {
                        output.push(VOWELS[rng.random_range(0..VOWELS.len())] as char);
                    }
                    letter_pos += 1;
                }
                _ => {
                    output.push(*p as char);
                }
            }
        }
    }

    output
}
