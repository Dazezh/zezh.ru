CREATE TABLE `link_items` (
  `id` int(11) NOT NULL COMMENT 'Первичный ключ',
  `link_id` int(11) NOT NULL COMMENT 'ID родительской ссылки',
  `url` text NOT NULL COMMENT 'URL элемента',
  `description` varchar(255) DEFAULT NULL COMMENT 'Описание ссылки',
  `position` int(11) NOT NULL DEFAULT 0 COMMENT 'Порядковый номер'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `short_links` (
  `id` int(11) NOT NULL COMMENT 'Первичный ключ',
  `short_code` varchar(20) NOT NULL COMMENT 'Короткий код ссылки',
  `original_url` text DEFAULT NULL COMMENT 'Оригинальная ссылка (NULL для мульти-ссылок)',
  `is_multi` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Является ли мульти-ссылкой',
  `click_count` int(11) NOT NULL DEFAULT 0 COMMENT 'Количество переходов',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Дата создания'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


ALTER TABLE `link_items`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_link_id` (`link_id`);

ALTER TABLE `short_links`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_short_code` (`short_code`);


ALTER TABLE `link_items`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Первичный ключ';

ALTER TABLE `short_links`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Первичный ключ';


ALTER TABLE `link_items`
  ADD CONSTRAINT `fk_link_items_link_id` FOREIGN KEY (`link_id`) REFERENCES `short_links` (`id`) ON DELETE CASCADE;
