use apple_password_gen::generate_with_rng;
use proptest::prelude::*;
use rand::{rngs::StdRng, SeedableRng};

// Contract from Apple's Password Rules Validation Tool, not a second generator:
// https://developer.apple.com/password-rules/scripts/generator.js
proptest! {
    #![proptest_config(ProptestConfig {
        cases: 512,
        failure_persistence: Some(Box::new(
            proptest::test_runner::FileFailurePersistence::WithSource("proptest-regressions")
        )),
        ..ProptestConfig::default()
    })]

    #[test]
    fn character_counts_and_digit_positions(seed in any::<[u8; 32]>()) {
        let password = generate_with_rng(StdRng::from_seed(seed));
        prop_assert!(password.is_ascii());
        prop_assert_eq!(password.len(), 20);
        prop_assert_eq!(password.bytes().filter(u8::is_ascii_uppercase).count(), 1);
        prop_assert_eq!(password.bytes().filter(u8::is_ascii_lowercase).count(), 16);
        prop_assert_eq!(password.bytes().filter(u8::is_ascii_digit).count(), 1);
        prop_assert_eq!(password.bytes().filter(|&c| c == b'-').count(), 2);
        prop_assert_eq!(password.as_bytes()[6], b'-');
        prop_assert_eq!(password.as_bytes()[13], b'-');
        let digit = password.bytes().position(|c| c.is_ascii_digit()).unwrap();
        prop_assert!([5, 7, 12, 14, 19].contains(&digit));
    }

    #[test]
    fn capital_letter_is_never_ambiguous(seed in any::<[u8; 32]>()) {
        let password = generate_with_rng(StdRng::from_seed(seed));
        prop_assert!(!password.contains(['l', 'L', 'O']));
    }

    #[test]
    fn digit_groups_preserve_syllables(seed in any::<[u8; 32]>()) {
        let password = generate_with_rng(StdRng::from_seed(seed));
        for group in password.split('-') {
            prop_assert_eq!(group.len(), 6);
            let letters: Vec<_> = group.bytes().filter(u8::is_ascii_alphabetic)
                .map(|c| c.to_ascii_lowercase()).collect();
            // Removing an end digit leaves CVC + CV; a full group is CVC + CVC.
            prop_assert!([5, 6].contains(&letters.len()));
            for (index, c) in letters.iter().enumerate() {
                let alphabet: &[u8] = if index % 3 == 1 {
                    b"aeiouy"
                } else {
                    b"bcdfghjkmnpqrstvwxz"
                };
                prop_assert!(alphabet.contains(c), "bad syllable in {}", password);
            }
        }
    }
}

#[test]
fn all_digit_positions_and_lowercase_o_remain_reachable() {
    let mut positions = std::collections::BTreeSet::new();
    let mut lowercase_o = false;
    for seed in 0..1024 {
        let password = generate_with_rng(StdRng::seed_from_u64(seed));
        positions.insert(password.bytes().position(|c| c.is_ascii_digit()).unwrap());
        lowercase_o |= password.contains('o');
    }
    assert_eq!(positions, [5, 7, 12, 14, 19].into_iter().collect());
    assert!(lowercase_o, "only uppercase O is excluded");
}
