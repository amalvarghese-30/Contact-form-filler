-- ============================================
-- RUN THIS SQL IN PHPMYADMIN NOW!
-- Database: form_insights
-- ============================================

-- Email Recipients Table
CREATE TABLE IF NOT EXISTS `notification_emails` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `email` VARCHAR(255) NOT NULL UNIQUE,
  `is_active` BOOLEAN DEFAULT TRUE,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Email Configuration Table
CREATE TABLE IF NOT EXISTS `email_config` (
  `id` INT PRIMARY KEY DEFAULT 1,
  `smtp_host` VARCHAR(255) DEFAULT 'smtp.gmail.com',
  `smtp_port` INT DEFAULT 587,
  `smtp_user` VARCHAR(255),
  `smtp_password` VARCHAR(255),
  `from_name` VARCHAR(255) DEFAULT 'Contact Form Filler',
  `is_enabled` BOOLEAN DEFAULT FALSE,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CHECK (`id` = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert default config row
INSERT INTO `email_config` (`id`, `is_enabled`) 
VALUES (1, FALSE)
ON DUPLICATE KEY UPDATE `id`=`id`;

-- ============================================
-- QUICK TEST: Add your email addresses here
-- ============================================
-- Uncomment and modify these lines to add your emails:

-- INSERT INTO `notification_emails` (`email`) VALUES ('your-email@gmail.com');
-- INSERT INTO `notification_emails` (`email`) VALUES ('admin@example.com');

-- Check your data:
-- SELECT * FROM notification_emails;
-- SELECT * FROM email_config;
