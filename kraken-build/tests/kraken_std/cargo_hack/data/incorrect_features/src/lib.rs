#[cfg(feature = "a")]
fn a() {}

#[cfg(feature = "a")]
fn b() {}

pub fn api() {
    #[cfg(feature = "a")]
    a();

    #[cfg(feature = "b")]
    b();
}
