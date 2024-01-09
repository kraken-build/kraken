#[cfg(feature = "a")]
fn a() {}

#[cfg(feature = "b")]
fn b() {}

pub fn api() {
    #[cfg(feature = "a")]
    a();

    #[cfg(feature = "b")]
    b();
}
