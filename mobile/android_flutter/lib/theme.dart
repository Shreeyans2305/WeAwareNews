import 'package:flutter/material.dart';

/// The same ink, paper and quiet gray palette used by the SwiftUI client.
ThemeData readingTheme(Brightness brightness) {
  final dark = brightness == Brightness.dark;
  final paper = dark ? const Color(0xff101010) : Colors.white;
  final ink = dark ? const Color(0xfff5f5f5) : const Color(0xff111111);
  final secondary = dark ? const Color(0xffaaaaaa) : const Color(0xff737373);
  final quiet = dark ? const Color(0xff202020) : const Color(0xfff5f5f5);
  final line = dark ? const Color(0xff333333) : const Color(0xffe7e7e7);
  final scheme = ColorScheme.fromSeed(seedColor: ink, brightness: brightness)
      .copyWith(
        primary: ink,
        onPrimary: paper,
        secondary: ink,
        onSecondary: paper,
        surface: paper,
        onSurface: ink,
        onSurfaceVariant: secondary,
        surfaceContainerLowest: paper,
        surfaceContainerLow: quiet,
        surfaceContainer: quiet,
        surfaceContainerHigh: quiet,
        surfaceContainerHighest: line,
        primaryContainer: quiet,
        onPrimaryContainer: ink,
        secondaryContainer: line,
        onSecondaryContainer: ink,
        outline: secondary,
        outlineVariant: line,
        surfaceTint: Colors.transparent,
      );
  final base = ThemeData(useMaterial3: true, colorScheme: scheme);
  return base.copyWith(
    scaffoldBackgroundColor: paper,
    textTheme: base.textTheme.apply(bodyColor: ink, displayColor: ink),
    appBarTheme: AppBarTheme(
      backgroundColor: paper,
      foregroundColor: ink,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: true,
      titleTextStyle: TextStyle(
        color: ink,
        fontSize: 17,
        fontWeight: FontWeight.w600,
      ),
    ),
    cardTheme: CardThemeData(
      color: paper,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: line),
      ),
    ),
    dividerTheme: DividerThemeData(color: line, thickness: 1, space: 28),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: quiet,
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(24),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(24),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(24),
        borderSide: BorderSide(color: ink),
      ),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: quiet,
      selectedColor: line,
      showCheckmark: false,
      side: BorderSide.none,
      shape: const StadiumBorder(),
      labelStyle: TextStyle(
        color: ink,
        fontSize: 13,
        fontWeight: FontWeight.w600,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: paper,
      surfaceTintColor: Colors.transparent,
      indicatorColor: line,
      elevation: 0,
      height: 76,
      labelTextStyle: WidgetStatePropertyAll(
        TextStyle(color: ink, fontSize: 11, fontWeight: FontWeight.w500),
      ),
      iconTheme: WidgetStatePropertyAll(IconThemeData(color: ink, size: 24)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: ink,
        foregroundColor: paper,
        minimumSize: const Size(48, 48),
        shape: const StadiumBorder(),
        elevation: 0,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: ink,
        side: BorderSide(color: line),
        minimumSize: const Size(48, 48),
        shape: const StadiumBorder(),
      ),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: paper,
      surfaceTintColor: Colors.transparent,
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: ink,
      linearTrackColor: line,
    ),
  );
}
