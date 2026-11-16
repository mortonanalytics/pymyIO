#!/usr/bin/env Rscript
# Converts myIO's bundled myDAR walk (vendor/myIO/data/mydar_iphone_walk.rda)
# into the files pymyio.mydar.mydar_iphone_walk() reads from
# src/pymyio/mydar/data/:
#   <table>.csv.gz  one per table (points, terrain, track, track_points,
#                   gps_fixes, pins, accuracy, trajectory)
#   orthophoto.png  the orthophoto bytes exactly as myIO ships them
#   walk.json       points n_total, terrain cell_size, orthophoto extent/size
#
# The values are the ones myIO ships, unchanged: doubles are written with 17
# significant digits so they read back bit for bit, and the script checks
# that before it finishes. Nothing is re-derived from a raw walk folder, and
# the walk is already in local coordinates with no origin or CRS (see
# vendor/myIO/data-raw/mydar_iphone_walk.R for what myIO stripped).
#
# The 500,000-point cloud is not converted: the wheel ships myIO's
# inst/extdata/mydar-iphone-walk-cloud.bin as is (see pyproject.toml).
#
# Run from the repository root:
#   Rscript data-raw/mydar_iphone_walk.R

out <- "src/pymyio/mydar/data"
load("vendor/myIO/data/mydar_iphone_walk.rda")
walk <- mydar_iphone_walk
stopifnot(inherits(walk, "mydar_walk"), all(is.na(walk$origin)), is.na(walk$crs),
          length(walk$features) == 0L)

num17 <- function(v) ifelse(is.na(v), NA_character_, sprintf("%.17g", v))

write_table <- function(df, name) {
  text <- df
  for (col in names(df)) {
    if (is.double(df[[col]])) text[[col]] <- num17(df[[col]])
  }
  quote <- which(vapply(df, is.character, logical(1)))
  path <- file.path(out, paste0(name, ".csv.gz"))
  con <- gzfile(path, "w", compression = 9)
  utils::write.csv(text, con, row.names = FALSE, na = "",
                   quote = if (length(quote)) quote else FALSE)
  close(con)

  # Read it back and require the same values. R's own number parser can land
  # one unit in the last place away from a 17-digit string, so doubles are
  # compared to 1e-15 here; Python's parser reads them back exactly.
  back <- utils::read.csv(path, colClasses = vapply(df, function(v) class(v)[1], character(1)),
                          na.strings = "", stringsAsFactors = FALSE)
  for (col in names(df)) {
    a <- df[[col]]
    b <- back[[col]]
    same <- identical(is.na(a), is.na(b)) && if (is.double(a)) {
      all(abs(a - b) <= 1e-15 * pmax(abs(a), 1), na.rm = TRUE)
    } else {
      identical(a[!is.na(a)], b[!is.na(b)])
    }
    if (!same) stop("round trip changed ", name, "$", col)
  }
  invisible(path)
}

for (name in c("points", "terrain", "track", "track_points", "gps_fixes", "pins",
               "accuracy", "trajectory")) {
  write_table(as.data.frame(walk[[name]]), name)
}
writeBin(walk$orthophoto$png, file.path(out, "orthophoto.png"))

json_num <- function(v) paste0("[", paste(sprintf("%.17g", v), collapse = ", "), "]")
writeLines(c(
  "{",
  sprintf('  "points_n_total": %d,', as.integer(attr(walk$points, "n_total"))),
  sprintf('  "terrain_cell_size": %s,', json_num(attr(walk$terrain, "cell_size"))),
  sprintf('  "orthophoto_extent": %s,', json_num(unname(walk$orthophoto$extent))),
  sprintf('  "orthophoto_size": %s', json_num(unname(walk$orthophoto$size))),
  "}"
), file.path(out, "walk.json"))

cat("wrote", out, "\n")
