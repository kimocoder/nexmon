# Vendored Android dependencies

These two artifacts were published to jcenter, which no longer serves them.
They are checked in with their original coordinates so `app/build.gradle` can
keep using the same GAVs and Gradle still resolves their transitive
dependencies (support libraries come from Google's Maven repository).

| Coordinate | Files | SHA-256 |
|---|---|---|
| `eu.chainfire:libsuperuser:1.0.0.201704021214` | `.aar`, `.pom` | aar `3d20d46b26d6ea9e668f01f52b088ce64808d4ef89d43ceae32b98b31337191f`, pom `aa0999d5bb140ac249a2683c949f9096e9ceaced91a2981c4fed638a7b9e5b59` |
| `com.nononsenseapps:filepicker:3.1.0` | `.aar`, `.pom` | aar `292863b28c0b8b27d3eb28a6cba88a8d65c04564f5919ead3617b88a5ec70f80`, pom `74da25f18014b0883776ea2f12c364c01eb45e0cd395ca3da526bb34382d41db` |

Both are Apache-2.0 licensed:

- libsuperuser: <https://github.com/Chainfire/libsuperuser>
- filepicker: <https://github.com/nononsenseapps/FilePicker> (archived)

The files were retrieved from the public jcenter mirror at
`https://maven.aliyun.com/repository/public/`. They are unmodified. If either
dependency is upgraded or replaced, delete the corresponding directory here and
remove the local-repo entry from `app/build.gradle`.