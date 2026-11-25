-- =======================================================
-- SmartRecover – Smart Lost and Found Management System
-- Database Schema for MySQL 5.7+ / MySQL 8.0+ / MySQL Workbench
-- =======================================================

CREATE DATABASE IF NOT EXISTS smartrecover_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smartrecover_db;

-- 1. INSTITUTIONS TABLE
CREATE TABLE IF NOT EXISTS institutions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    domain VARCHAR(100),
    location VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    institution_id INT NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(180) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    contact_number VARCHAR(50),
    role ENUM('user', 'admin') DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE RESTRICT,
    INDEX idx_user_institution (institution_id),
    INDEX idx_user_email (email)
) ENGINE=InnoDB;

-- 3. ITEMS TABLE (Lost and Found reports)
CREATE TABLE IF NOT EXISTS items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    institution_id INT NOT NULL,
    user_id INT NOT NULL,
    type ENUM('lost', 'found') NOT NULL,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    date_event DATE NOT NULL,
    location VARCHAR(255) NOT NULL,
    photo_filename VARCHAR(255) DEFAULT NULL,
    private_details TEXT DEFAULT NULL,
    status ENUM('reported', 'match_found', 'claim_submitted', 'under_verification', 'approved', 'recovered', 'closed') DEFAULT 'reported',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_item_inst_type (institution_id, type),
    INDEX idx_item_category (category),
    INDEX idx_item_status (status)
) ENGINE=InnoDB;

-- 4. MATCHES TABLE (Stores calculated smart match pairings)
CREATE TABLE IF NOT EXISTS matches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    institution_id INT NOT NULL,
    lost_item_id INT NOT NULL,
    found_item_id INT NOT NULL,
    score DECIMAL(5,2) NOT NULL,
    factor_name DECIMAL(5,2) DEFAULT 0,
    factor_category DECIMAL(5,2) DEFAULT 0,
    factor_description DECIMAL(5,2) DEFAULT 0,
    factor_location DECIMAL(5,2) DEFAULT 0,
    factor_date DECIMAL(5,2) DEFAULT 0,
    status VARCHAR(50) DEFAULT 'suggested',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (lost_item_id) REFERENCES items(id) ON DELETE CASCADE,
    FOREIGN KEY (found_item_id) REFERENCES items(id) ON DELETE CASCADE,
    UNIQUE KEY uq_lost_found (lost_item_id, found_item_id),
    INDEX idx_matches_inst (institution_id),
    INDEX idx_matches_score (score)
) ENGINE=InnoDB;

-- 5. CLAIMS TABLE (Ownership verification requests)
CREATE TABLE IF NOT EXISTS claims (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    claimant_id INT NOT NULL,
    proof_details TEXT NOT NULL,
    contact_phone VARCHAR(50) DEFAULT NULL,
    status ENUM('pending', 'under_review', 'approved', 'rejected') DEFAULT 'pending',
    reviewer_id INT DEFAULT NULL,
    review_notes TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    FOREIGN KEY (claimant_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_claims_item (item_id),
    INDEX idx_claims_claimant (claimant_id),
    INDEX idx_claims_status (status)
) ENGINE=InnoDB;

-- 6. NOTIFICATIONS TABLE
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    link VARCHAR(255) DEFAULT NULL,
    is_read TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notif_user_read (user_id, is_read)
) ENGINE=InnoDB;

-- =======================================================
-- SAMPLE DATA FOR DEVELOPMENT AND TESTING
-- Passwords below are hashed for 'password123'
-- Werkzeug scrypt hash for 'password123':
-- scrypt:32768:8:1$c7qpC0jcErv2ATsl$0fc79c6583d8c81e489715aba7d696baf8f19237694c0ef4e6bfb1f9e98408d81499a6be1ddd123defba4e7fe87a5bbd51a805ad763e131b0220ebd5209d90ae
-- =======================================================

INSERT INTO institutions (id, name, code, domain, location) VALUES
(1, 'Apex Institute of Engineering & Technology', 'AIET', 'aiet.edu', 'North Campus, Building 4'),
(2, 'Metro State University', 'MSU', 'metrostate.edu', 'Downtown Campus, Academic Block A'),
(3, 'City Polytechnic College', 'CPC', 'citypoly.edu', 'West Bay Wing')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Sample Users:
-- Admin: admin@aiet.edu / password123
-- Student 1: ayush@aiet.edu / password123
-- Student 2: rahul@aiet.edu / password123
INSERT INTO users (id, institution_id, full_name, email, password_hash, contact_number, role) VALUES
(1, 1, 'Prof. Sharma (Admin)', 'admin@aiet.edu', 'scrypt:32768:8:1$c7qpC0jcErv2ATsl$0fc79c6583d8c81e489715aba7d696baf8f19237694c0ef4e6bfb1f9e98408d81499a6be1ddd123defba4e7fe87a5bbd51a805ad763e131b0220ebd5209d90ae', '+91 9876543210', 'admin'),
(2, 1, 'Ayush Sharma', 'ayush@aiet.edu', 'scrypt:32768:8:1$c7qpC0jcErv2ATsl$0fc79c6583d8c81e489715aba7d696baf8f19237694c0ef4e6bfb1f9e98408d81499a6be1ddd123defba4e7fe87a5bbd51a805ad763e131b0220ebd5209d90ae', '+91 9123456780', 'user'),
(3, 1, 'Rahul Verma', 'rahul@aiet.edu', 'scrypt:32768:8:1$c7qpC0jcErv2ATsl$0fc79c6583d8c81e489715aba7d696baf8f19237694c0ef4e6bfb1f9e98408d81499a6be1ddd123defba4e7fe87a5bbd51a805ad763e131b0220ebd5209d90ae', '+91 9234567891', 'user')
ON DUPLICATE KEY UPDATE full_name=VALUES(full_name);
