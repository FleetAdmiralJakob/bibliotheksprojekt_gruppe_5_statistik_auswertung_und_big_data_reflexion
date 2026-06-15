-- Value placeholders are rendered from shared/domain_values.py before execution.

DROP TABLE IF EXISTS borrowings;
DROP TABLE IF EXISTS book_authors;
DROP TABLE IF EXISTS book_copies;
DROP TABLE IF EXISTS books;
DROP TABLE IF EXISTS publishers;
DROP TABLE IF EXISTS authors;
DROP TABLE IF EXISTS users;

-- TODO: Create indexes for the stuff we query for

CREATE TABLE authors (
    author_id TEXT PRIMARY KEY,
    name TEXT
);

CREATE TABLE publishers (
    publisher_id TEXT PRIMARY KEY,
    name TEXT,
    location TEXT
);

-- Only students
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    -- Email from parents or students (for the case that the student does not have an email)
    email TEXT
);

-- If books have a hard and a soft copy, they are both saved as separate entries in the books table as they have different ISBNs.
CREATE TABLE books (
    isbn TEXT PRIMARY KEY,
    title TEXT,
    -- One book, one category
    main_category TEXT CHECK (main_category IN ({{MAIN_CATEGORIES}})),
    language TEXT,
    publisher_id TEXT,
    release_date TEXT,
    page_count INTEGER CHECK (page_count > 0),
    FOREIGN KEY (publisher_id) REFERENCES publishers(publisher_id)
);

CREATE TABLE book_authors (
    isbn TEXT,
    author_id TEXT,
    PRIMARY KEY (isbn, author_id),
    FOREIGN KEY (isbn) REFERENCES books(isbn),
    FOREIGN KEY (author_id) REFERENCES authors(author_id)
);

CREATE TABLE book_copies (
    copy_id TEXT PRIMARY KEY,
    isbn TEXT,
    state TEXT CHECK (state IN ({{COPY_STATES}})),
    availability TEXT CHECK (availability IN ({{COPY_AVAILABILITIES}})),
    FOREIGN KEY (isbn) REFERENCES books(isbn)
);

CREATE TABLE borrowings (
    borrowing_id TEXT PRIMARY KEY,
    user_id TEXT,
    copy_id TEXT,
    borrow_date TEXT,
    -- Return date will be calculated off the borrow date
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (copy_id) REFERENCES book_copies(copy_id)
);
