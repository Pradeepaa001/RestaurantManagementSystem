-- Add bill_status column to orders table
ALTER TABLE orders ADD COLUMN bill_status ENUM('pending', 'requested', 'paid') DEFAULT 'pending'; 